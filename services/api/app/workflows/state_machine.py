"""State machine sản xuất video. Chỉ cho phép chuyển trạng thái hợp lệ; mọi bước có log + audit."""
from dataclasses import dataclass

from app.core import audit
from app.core.context import Ctx
from app.core.errors import InvalidTransition
from app.modules.projects.models import Project, WorkflowEvent

MAIN_FLOW = [
    "CREATED", "SCRIPT_GENERATING", "SCRIPT_REVIEW", "STORYBOARD_READY", "ASSET_VALIDATION", "GENERATION_QUEUED",
    "GENERATING", "SCENE_QC", "RENDERING", "FINAL_QC", "APPROVAL_PENDING", "APPROVED", "PUBLISH_QUEUED", "PUBLISHED",
    "ANALYTICS_COLLECTION", "FEEDBACK_REVIEW",
]
EXCEPTION_STATES = ["FAILED", "CANCELLED", "RETRY_PENDING", "NEEDS_MANUAL_ACTION"]
ALL_STATES = MAIN_FLOW + EXCEPTION_STATES
RETRYABLE = {"SCRIPT_GENERATING", "GENERATING", "RENDERING", "PUBLISH_QUEUED"}
TERMINAL = {"CANCELLED"}
NON_CANCELLABLE = {"PUBLISHED", "ANALYTICS_COLLECTION", "FEEDBACK_REVIEW", "CANCELLED"}

TRANSITIONS: dict[str, set[str]] = {
    "CREATED": {"SCRIPT_GENERATING"},
    "SCRIPT_GENERATING": {"SCRIPT_REVIEW", "FAILED", "RETRY_PENDING"},
    "SCRIPT_REVIEW": {"STORYBOARD_READY", "SCRIPT_GENERATING"},
    "STORYBOARD_READY": {"ASSET_VALIDATION", "SCRIPT_REVIEW"},
    "ASSET_VALIDATION": {"GENERATION_QUEUED", "NEEDS_MANUAL_ACTION", "STORYBOARD_READY"},
    "GENERATION_QUEUED": {"GENERATING", "NEEDS_MANUAL_ACTION"},
    "GENERATING": {"SCENE_QC", "FAILED", "RETRY_PENDING", "NEEDS_MANUAL_ACTION"},
    "SCENE_QC": {"RENDERING", "GENERATING", "NEEDS_MANUAL_ACTION"},
    "RENDERING": {"FINAL_QC", "FAILED", "RETRY_PENDING"},
    "FINAL_QC": {"APPROVAL_PENDING", "RENDERING", "GENERATING", "SCENE_QC"},
    "APPROVAL_PENDING": {"APPROVED", "FINAL_QC", "GENERATING"},
    "APPROVED": {"PUBLISH_QUEUED", "FINAL_QC"},
    "PUBLISH_QUEUED": {"PUBLISHED", "FAILED", "APPROVED"},
    "PUBLISHED": {"ANALYTICS_COLLECTION"},
    "ANALYTICS_COLLECTION": {"FEEDBACK_REVIEW"},
    "FEEDBACK_REVIEW": {"ANALYTICS_COLLECTION"},
    "FAILED": {"RETRY_PENDING"},
    "RETRY_PENDING": {"SCRIPT_GENERATING", "GENERATING", "RENDERING", "PUBLISH_QUEUED"},
    "NEEDS_MANUAL_ACTION": {"ASSET_VALIDATION", "GENERATION_QUEUED", "GENERATING", "SCENE_QC", "STORYBOARD_READY"},
    "CANCELLED": set(),
}
for _s in ALL_STATES:
    if _s not in NON_CANCELLABLE:
        TRANSITIONS[_s].add("CANCELLED")


@dataclass(frozen=True)
class StepSpec:
    label: str
    owner: str  # Agent hoặc vai trò chịu trách nhiệm
    input: str
    output: str
    permission: str | None


STEPS: dict[str, StepSpec] = {
    "CREATED": StepSpec("Khởi tạo", "Content Creator", "Brief (M02)", "Project", "project.create"),
    "SCRIPT_GENERATING": StepSpec("Đang viết kịch bản", "A02 AI Script", "Brief + Brand DNA", "3 ý tưởng + kịch bản", "script.generate"),
    "SCRIPT_REVIEW": StepSpec("Duyệt kịch bản", "Production Manager", "Script version", "Script approved", "script.approve"),
    "STORYBOARD_READY": StepSpec("Storyboard sẵn sàng", "A03 AI Prompt", "Scenes", "Prompt 9 phần/cảnh", "script.edit"),
    "ASSET_VALIDATION": StepSpec("Kiểm tra tài nguyên", "A04 AI Character", "Locks + assets", "Báo cáo hợp lệ", "generation.run"),
    "GENERATION_QUEUED": StepSpec("Chờ tạo cảnh", "A05 AI Video", "Prompt + provider", "Generation jobs", "generation.run"),
    "GENERATING": StepSpec("Đang tạo cảnh", "A05 AI Video", "Generation jobs", "Scene clips", "generation.run"),
    "SCENE_QC": StepSpec("QC từng cảnh", "A07 AI QC + QC Reviewer", "Scene clips", "Cảnh đạt/không đạt", "qc.review"),
    "RENDERING": StepSpec("Đang dựng video", "A06 AI Editor", "Timeline", "MP4 + thumbnail + SRT", "render.run"),
    "FINAL_QC": StepSpec("QC tổng thể", "A07 AI QC + QC Reviewer", "Render", "Điểm 10 tiêu chí", "qc.review"),
    "APPROVAL_PENDING": StepSpec("Chờ phê duyệt", "Production Manager / CEO", "QC đạt ≥ ngưỡng", "Quyết định", "project.approve"),
    "APPROVED": StepSpec("Đã duyệt", "Publisher", "Render approved", "Lịch đăng", "publish.manage"),
    "PUBLISH_QUEUED": StepSpec("Chờ xuất bản", "Publisher", "Publication", "Bài đăng", "publish.execute"),
    "PUBLISHED": StepSpec("Đã xuất bản", "Publisher", "URL bài đăng", "Theo dõi", "publish.execute"),
    "ANALYTICS_COLLECTION": StepSpec("Thu thập số liệu", "A10 AI Analytics", "Số liệu nền tảng", "Snapshots", "analytics.enter"),
    "FEEDBACK_REVIEW": StepSpec("Rà soát phản hồi", "A08 AI Feedback", "Analytics + bình luận", "Feedback cases", "feedback.create"),
    "FAILED": StepSpec("Lỗi", "Production Manager", "Lỗi", "Retry/Huỷ", None),
    "CANCELLED": StepSpec("Đã huỷ", "Production Manager", "-", "-", "project.cancel"),
    "RETRY_PENDING": StepSpec("Chờ chạy lại", "A01 AI Director", "Bước lỗi", "Chạy lại", None),
    "NEEDS_MANUAL_ACTION": StepSpec("Cần thao tác thủ công", "Production Manager", "Vấn đề", "Xử lý", None),
}

PROGRESS = {s: int(i * 100 / (len(MAIN_FLOW) - 1)) for i, s in enumerate(MAIN_FLOW)}


def can_transition(current: str, target: str) -> bool:
    return target in TRANSITIONS.get(current, set())


def transition(ctx: Ctx, project: Project, target: str, *, note: str = "", payload: dict | None = None) -> WorkflowEvent:
    current = project.status
    if not can_transition(current, target):
        raise InvalidTransition(
            f"Không thể chuyển {current} → {target}",
            details={"current": current, "target": target, "allowed": sorted(TRANSITIONS.get(current, set()))},
        )
    if target in ("FAILED", "RETRY_PENDING") and current in RETRYABLE:
        project.resume_status = current  # ghi nhớ bước lỗi để retry đúng bước
    elif target == "RETRY_PENDING" and not project.resume_status:
        project.resume_status = "GENERATING"
    if current == "RETRY_PENDING" and target != "CANCELLED":
        if project.resume_status and target != project.resume_status:
            raise InvalidTransition(f"Chỉ được chạy lại bước {project.resume_status}",
                                    details={"current": current, "target": target})
        project.retry_count += 1
    project.status = target
    if target in PROGRESS:
        project.progress = PROGRESS[target]
    ev = WorkflowEvent(project_id=project.id, from_status=current, to_status=target, actor_type=ctx.actor.type,
                       actor_ref=ctx.actor.id, note=note[:2000], payload=payload or {})
    ctx.db.add(ev)
    audit.record(ctx, "workflow.transition", "project", project.id, before={"status": current}, after={"status": target, "note": note})
    return ev


def describe() -> dict:
    return {
        "main_flow": MAIN_FLOW,
        "exception_states": EXCEPTION_STATES,
        "transitions": {k: sorted(v) for k, v in TRANSITIONS.items()},
        "steps": {k: v.__dict__ for k, v in STEPS.items()},
    }
