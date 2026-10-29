# Kiến trúc — Ánh Ngân AI Video Studio V2.0

## 1. Tổng quan

**Modular Monolith + Background Workers.** Một backend FastAPI chứa 12 module nghiệp vụ độc lập, dùng chung một PostgreSQL; tác vụ nặng (tạo cảnh, render FFmpeg) chạy ở Celery worker qua Redis. Frontend Next.js gọi API qua cookie httpOnly (cùng origin sau gateway Nginx).

```
                 ┌──────────────────────── Gateway Nginx (:8080) ────────────────────────┐
 Trình duyệt ──► │  /            → web (Next.js 15, 15 màn hình)                        │
                 │  /api/v1/*    → api (FastAPI, 12 module, 10 Agent, RBAC, audit)       │
                 └───────────────────────────────┬───────────────────────────────────────┘
                                                 │
            ┌──────────────┬─────────────────────┼──────────────────┬───────────────────┐
            ▼              ▼                     ▼                  ▼                   ▼
      PostgreSQL 16     Redis 7          Celery worker(s)      Celery beat      Object Storage
      45 bảng, trigger  broker + rate    generation / render   recover 5 phút   Volume / S3 (tuỳ chọn)
      bất biến          limit            FFmpeg + FFprobe
                                                 │
                         ┌───────────────────────┼─────────────────────────┐
                         ▼                       ▼                         ▼
                 MockVideoProvider      ManualFlowProvider          RealAPIProvider
                 (DEMO, MP4 thật)       (upload từ Google Flow)     (API chính thức — chưa kết nối)
```

## 2. 12 module nghiệp vụ (`services/api/app/modules/`)

| Mã | Module | Thư mục | Bảng chính | Màn hình |
|---|---|---|---|---|
| B01 | Project Manager (+ Kênh & Brand DNA) | `projects` | channels, brand_profiles, projects, production_batches, workflow_events | M02, M11, M13 |
| B02 | AI Script Engine | `scripts` | scripts, script_versions, scenes, scene_versions | M03 |
| B03 | Character & Voice Manager | `characters` | characters, character_references, character_locks, voice_profiles, voice_locks, scene_locks | M04 |
| B04 | Prompt Engine | `prompts` | prompt_templates, prompt_versions | M03, M09 |
| B05 | Video Generation Manager | `generation` | generation_jobs | M05 |
| B06 | Render Engine | `rendering` | render_jobs, renders | M06 |
| B07 | Quality Control Engine | `quality` | qc_reviews, qc_findings, approvals | M07 |
| B08 | Feedback Loop Engine | `feedback` | feedback_cases, feedback_events, root_cause_analyses, capa_actions, verification_results | M08 |
| B09 | AI Lessons Learned Engine | `learning` | lessons_learned | M09 |
| B10 | Publishing Manager | `publishing` | publications | M10 |
| B11 | Analytics Engine | `analytics` | analytics_snapshots | M01, M10 |
| B12 | Administration & Cost Manager | `administration` | users, roles, permissions, audit_logs, provider_accounts, budget_limits, cost_records, notifications, system_settings, backups | M15 |

Hạ tầng dùng chung (không phải module nghiệp vụ): `app/media` (thư viện tài nguyên M12, Object Storage, kiểm tra file), `app/agents` (Agent Registry M14), `app/providers` (adapter LLM/video/publishing), `app/workflows` (state machine, orchestrator A01, dispatch, tác vụ nền), `app/core` (config, bảo mật, RBAC, audit, rate limit).

Mỗi module gồm `models.py` · `schemas.py`/schema trong router · `service.py` (nghiệp vụ + validation + kiểm tra quyền) · `router.py` (API) · test trong `tests/`.

## 3. 10 AI Agent (`app/agents/registry.py`)

| Mã | Agent | Kiểu | Phạm vi được phép (allowed_actions) |
|---|---|---|---|
| A01 | AI Director | rule-engine | workflow.advance, workflow.retry, project.orchestrate |
| A02 | AI Script | LLM (Mock ở DEMO / Claude ở PRODUCTION) | script.ideas, script.write, script.storyboard |
| A03 | AI Prompt | rule-engine (Jinja sandbox) | prompt.build |
| A04 | AI Character | rule-engine | assets.validate, character.check |
| A05 | AI Video | rule-engine + Video Provider | generation.submit, generation.poll |
| A06 | AI Editor | rule-engine + FFmpeg | render.plan, render.execute, subtitle.generate |
| A07 | AI QC | rule-engine (FFprobe, EBU R128, blackdetect, compliance) | qc.scene_check, qc.final_check |
| A08 | AI Feedback | LLM + quy tắc | feedback.create_from_qc, feedback.triage_suggest, feedback.rca_suggest |
| A09 | AI Learning | LLM | lesson.draft, lesson.search |
| A10 | AI Analytics | rule-engine (thống kê xác định) | analytics.compute, analytics.insights |

- Mọi lần chạy đi qua `run_agent()`: kiểm tra action ∈ allowed_actions (vi phạm → 403 + audit), agent bật/tắt, giới hạn lượt/ngày, ngân sách trước khi gọi LLM thật; ghi `agent_executions` (model, provider, prompt version, input/output ref, token, chi phí, latency, trạng thái, lỗi). Bản ghi RUNNING được ghi bằng session độc lập nên log lỗi không mất khi transaction chính rollback.
- **Không agent nào có quyền phê duyệt, xuất bản hay sửa cấu hình chuẩn.** Phép tính tài chính/KPI luôn là code xác định.
- Agent dùng chung hạ tầng mô hình qua `LLMProvider` (Mock / Anthropic). Không cần 10 mô hình riêng.

## 4. Workflow (`app/workflows/state_machine.py`)

16 trạng thái chính + 4 ngoại lệ; chỉ cho phép chuyển trạng thái hợp lệ (bảng `TRANSITIONS`), mỗi lần chuyển ghi `workflow_events` + `audit_logs`. Chi tiết: [docs/architecture/WORKFLOW.md](WORKFLOW.md).

## 5. Video Engine

- `VideoProvider` interface: `submit_generation · get_status · get_result · cancel_job · estimate_cost · validate_capabilities`.
- **MockVideoProvider**: tạo MP4 thật bằng FFmpeg (9:16, 8s, chữ tiếng Việt, âm thanh), hỗ trợ tiêm lỗi `[[MOCK_FAIL]]`, `[[MOCK_FAIL_ONCE]]`, `[[MOCK_TIMEOUT]]`, `[[MOCK_UNAVAILABLE]]`. Chỉ dùng ở DEMO; chi phí là **mô phỏng** (1.500 VND/giây).
- **ManualFlowProvider**: Google Flow không có API công khai → tạo phiếu chờ, người dùng tải clip lên M05; hệ thống kiểm tra tỉ lệ 9:16, độ phân giải ≥ 720×1280, thời lượng 2–30s, gắn Scene ID. Không dùng cookie/token phiên.
- **RealAPIProvider**: adapter REST cấu hình được cho API chính thức (Veo/Vertex AI…). Trạng thái *chưa kết nối* cho tới khi có key + xác minh.
- **Render Engine** (`modules/rendering/ffmpeg.py`): một lệnh `filter_complex` — trim, scale/pad 1080×1920, 30fps, concat, burn phụ đề SRT (libass), logo overlay, voice-over (adelay), nhạc nền (loop, volume, fade), amix, loudnorm EBU R128 → MP4 H.264/AAC faststart + thumbnail + SRT. Kết quả được FFprobe kiểm tra lại.

## 6. Dữ liệu & bảo mật

- 45 bảng, UUID PK, FK, index, timestamp, soft delete, version history. DDL đóng băng tại `migrations/sql/0001_initial_schema.sql`; migration 0002 thêm trigger: Lock/prompt/script version đã duyệt **bất biến**, `audit_logs` **chỉ ghi thêm**.
- **DEMO/PRODUCTION**: cột `data_mode` trên mọi dữ liệu nghiệp vụ; truy vấn luôn lọc theo chế độ hiện hành. Prompt template có con trỏ kích hoạt riêng cho từng chế độ. DEMO không gọi API tính phí, không tự xuất bản; PRODUCTION không cho Mock provider.
- Xác thực: Argon2, JWT trong cookie httpOnly SameSite=Lax + CSRF double-submit; token gắn dấu băm mật khẩu (đổi mật khẩu → thu hồi phiên); khoá tài khoản sau 5 lần sai; rate limit (Redis) cho login và toàn API.
- RBAC 8 vai trò × 55 quyền (`app/core/permissions.py`), kiểm tra ở cả router và service; nguyên tắc 4 mắt cho duyệt Lock và CAPA.
- Secret nhà cung cấp mã hoá Fernet, chỉ hiển thị 4 ký tự cuối; audit log tự che trường nhạy cảm.
- Upload: whitelist đuôi file + kiểm tra magic bytes + giới hạn dung lượng + FFprobe + SHA-256; tên file được làm sạch; file media ở Object Storage, DB chỉ lưu metadata.
- Chi phí: `check_budget()` trước mọi thao tác phát sinh chi phí (dự án / kênh / toàn hệ thống / nhà cung cấp, ngưỡng cảnh báo, hard stop) → `cost_records`.

## 7. Độ tin cậy

- Tác vụ nền idempotent: `FOR UPDATE SKIP LOCKED`, trạng thái kết thúc → bỏ qua, job đã SUBMITTED chỉ poll (không gửi lại, không tính phí 2 lần).
- Gửi tác vụ **sau commit** (`workflows/dispatch.py`) → worker không đọc dữ liệu chưa commit.
- `acks_late` + `reject_on_worker_lost`; beat chạy `recover_stuck_jobs` mỗi 5 phút; API `/jobs/recover`.
- Retry tự động có giới hạn (mặc định 3 lần/phiên bản cảnh, render 2 lần); vượt giới hạn → `NEEDS_MANUAL_ACTION` / `FAILED` kèm lý do; retry dự án chạy lại đúng bước lỗi.
- Quan sát: log JSON, `X-Request-ID`, Prometheus `/metrics`, `/health/ready` (DB, Redis, FFmpeg, storage, worker).
