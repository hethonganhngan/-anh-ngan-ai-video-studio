# Workflow sản xuất video

```mermaid
stateDiagram-v2
    [*] --> CREATED
    CREATED --> SCRIPT_GENERATING: A02 tạo 3 ý tưởng
    SCRIPT_GENERATING --> SCRIPT_REVIEW: A02 viết kịch bản / viết tay
    SCRIPT_REVIEW --> SCRIPT_GENERATING: tạo lại
    SCRIPT_REVIEW --> STORYBOARD_READY: PM duyệt (script.approve) + A03 lắp prompt
    STORYBOARD_READY --> ASSET_VALIDATION: A04 kiểm tra Lock/consent/tài nguyên/ngân sách
    ASSET_VALIDATION --> GENERATION_QUEUED: hợp lệ
    ASSET_VALIDATION --> NEEDS_MANUAL_ACTION: thiếu điều kiện
    GENERATION_QUEUED --> GENERATING: A05 gửi provider
    GENERATING --> SCENE_QC: đủ cảnh
    GENERATING --> NEEDS_MANUAL_ACTION: chờ Flow / hết retry / chặn ngân sách
    NEEDS_MANUAL_ACTION --> GENERATING: đã xử lý
    SCENE_QC --> RENDERING: mọi cảnh đạt (A06)
    SCENE_QC --> GENERATING: tạo lại cảnh lỗi
    RENDERING --> FINAL_QC: MP4 hợp lệ (A07 đo tự động)
    RENDERING --> FAILED: hết retry render
    FINAL_QC --> APPROVAL_PENDING: QC người chấm ≥ 98, không lỗi nghiêm trọng mở
    APPROVAL_PENDING --> APPROVED: người có project.approve
    APPROVAL_PENDING --> FINAL_QC: từ chối (có lý do)
    APPROVED --> PUBLISH_QUEUED: xuất gói / lên lịch
    PUBLISH_QUEUED --> PUBLISHED: ghi URL bài đăng
    PUBLISHED --> ANALYTICS_COLLECTION: nhập số liệu
    ANALYTICS_COLLECTION --> FEEDBACK_REVIEW
    FEEDBACK_REVIEW --> ANALYTICS_COLLECTION
    FAILED --> RETRY_PENDING
    RETRY_PENDING --> SCRIPT_GENERATING
    RETRY_PENDING --> GENERATING
    RETRY_PENDING --> RENDERING
```

Mọi trạng thái trước PUBLISHED đều có thể → `CANCELLED` (cần quyền `project.cancel` và lý do).

| Bước | Đầu vào | Đầu ra | Phụ trách | Quyền | Retry | Chi phí |
|---|---|---|---|---|---|---|
| CREATED | Brief M02 | Project (idempotency key) | Content Creator | project.create | — | ước tính trước |
| SCRIPT_GENERATING | Brief + Brand DNA + prompt A02 | 3 ý tưởng có điểm, kịch bản | A02 | script.generate | retry dự án | LLM (thật ở PRODUCTION) |
| SCRIPT_REVIEW | Script version | Duyệt / sửa → version mới | PM | script.approve | — | — |
| STORYBOARD_READY | Scenes | Prompt 9 phần/cảnh | A03 | script.edit | dựng lại prompt | — |
| ASSET_VALIDATION | Lock, consent, asset, provider, ngân sách | Báo cáo blocking/warnings | A04 | generation.run | kiểm tra lại | kiểm tra ngân sách |
| GENERATION_QUEUED / GENERATING | Prompt + provider | Clip cảnh (asset) | A05 | generation.run | tự động 3 lần/phiên bản | cost_records VIDEO_GEN |
| SCENE_QC | Clip | QC_PASSED/QC_FAILED | A07 + QC Reviewer | qc.review | tạo lại cảnh | — |
| RENDERING | Timeline M06 | MP4 + SRT + thumbnail | A06 | render.run | tự động 2 lần, retry dự án | — |
| FINAL_QC | Render | Điểm 10 tiêu chí | A07 (gợi ý) + QC Reviewer | qc.review | chấm lại | — |
| APPROVAL_PENDING | QC PASS | Approval | PM / CEO | project.approve | — | — |
| APPROVED → PUBLISHED | Render đã duyệt | Gói xuất / bài đăng | Publisher | publish.* | — | — |
| ANALYTICS_COLLECTION | Số liệu nền tảng | Snapshots, KPI | A10 + Publisher | analytics.enter | — | — |
| FEEDBACK_REVIEW | Analytics, bình luận | Feedback cases | A08 | feedback.create | — | — |

## Feedback Loop 360°

```
INTAKE(NEW) → VALIDATE(VALIDATED, cần bằng chứng) → TRIAGE(RCA_PENDING, P0–P3 + owner + deadline + KPI)
→ ROOT CAUSE(5 Whys, FACT/HYPOTHESIS/UNKNOWN, mức chắc chắn) → CAPA(ACTION_APPROVED, ≥1 CORRECTIVE, người khác duyệt)
→ ASSIGN(IN_PROGRESS, mọi CAPA có owner+deadline, hoàn thành cần bằng chứng) → VERIFY(VERIFY_PENDING → VERIFIED | REOPENED)
→ STANDARDIZE(STANDARDIZED, ghi chú chuẩn hoá + bài học nháp) → CLOSED (bắt buộc bằng chứng + kiểm chứng đạt)
```
Bài học (M09): DRAFT → PENDING_APPROVAL → APPROVED → APPLIED (tạo prompt version mới, kích hoạt theo chế độ) → ROLLED_BACK.
