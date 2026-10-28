"""ManualFlowProvider — người dùng tạo cảnh trên Google Flow (giao diện web) rồi TẢI LÊN thủ công.

Google Flow không có API công khai → hệ thống KHÔNG tự động hoá Flow, không dùng cookie/token phiên.
submit_generation chỉ tạo phiếu chờ; tác vụ chuyển NEEDS_MANUAL_ACTION cho đến khi file được nhập & kiểm tra.
"""
import uuid
from decimal import Decimal

from app.providers.video.base import GenerationSpec, ProviderError, ProviderStatus, VideoProvider

# Tiêu chí nhận file Flow
MIN_WIDTH, MIN_HEIGHT = 720, 1280
ASPECT_TOLERANCE = 0.03
MIN_DURATION, MAX_DURATION = 2.0, 30.0


class ManualFlowProvider(VideoProvider):
    code = "manual_flow"
    name = "Google Flow (nhập thủ công)"
    kind = "MANUAL"
    is_real = False
    unit_cost_vnd_per_sec = Decimal(0)  # chi phí gói Flow nhập tay khi import (nếu có)
    max_duration_sec = 8
    supported_aspects = ("9:16",)

    def submit_generation(self, spec: GenerationSpec) -> str:
        return f"flow-manual-{uuid.uuid4().hex[:12]}"

    def get_status(self, provider_job_id):
        return ProviderStatus(state="NEEDS_MANUAL_ACTION", progress=0,
                              error_message="Chờ tải video cảnh từ Google Flow lên hệ thống")

    def get_result(self, provider_job_id):
        raise ProviderError("Kết quả Flow phải được nhập thủ công", code="MANUAL_IMPORT_REQUIRED", retryable=False)

    def cancel_job(self, provider_job_id):
        return True


def validate_flow_clip(info: dict, target_aspect: str = "9:16", target_duration: int = 8) -> tuple[list[str], list[str]]:
    """Trả về (errors, warnings) cho clip nhập từ Flow."""
    errors, warnings = [], []
    w, h, d = info.get("width") or 0, info.get("height") or 0, info.get("duration_sec") or 0
    if not w or not h:
        errors.append("Không đọc được kích thước video")
        return errors, warnings
    tw, th = (int(x) for x in target_aspect.split(":"))
    if abs(w / h - tw / th) > ASPECT_TOLERANCE:
        errors.append(f"Tỉ lệ {w}x{h} không phải {target_aspect}")
    if w < MIN_WIDTH or h < MIN_HEIGHT:
        errors.append(f"Độ phân giải {w}x{h} thấp hơn tối thiểu {MIN_WIDTH}x{MIN_HEIGHT}")
    elif h < 1920:
        warnings.append(f"Độ phân giải {w}x{h} < 1080x1920, sẽ được upscale khi render")
    if d < MIN_DURATION or d > MAX_DURATION:
        errors.append(f"Thời lượng {d:.1f}s ngoài khoảng {MIN_DURATION:.0f}-{MAX_DURATION:.0f}s")
    elif abs(d - target_duration) > 1.0:
        warnings.append(f"Thời lượng {d:.1f}s khác mục tiêu {target_duration}s")
    if not info.get("has_audio"):
        warnings.append("Clip không có âm thanh")
    return errors, warnings
