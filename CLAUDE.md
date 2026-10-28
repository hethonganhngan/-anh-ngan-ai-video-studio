# CLAUDE.md — Hướng dẫn cho phiên Claude Code tiếp theo

Dự án: **Ánh Ngân AI Video Studio V2.0**. Trước khi làm gì: đọc `docs/architecture/PROJECT_STATUS.md` (trạng thái, việc tiếp theo) và `docs/architecture/DECISION_LOG.md`. **Không tạo lại dự án, không ghi đè dữ liệu**, không đổi phạm vi đã chốt (15 màn hình, 12 module, 10 agent).

## Lệnh thường dùng
- Môi trường Python: `.venv/` ở gốc repo. Chạy lệnh backend từ `services/api` (Alembic dùng `alembic.ini` ở đó).
- Test backend: `.venv/bin/python -m pytest -q -p no:warnings` (DB `anngan_test`, tự reset schema; ~3 phút; có render MP4 thật).
- Lint: `.venv/bin/ruff check services tests`.
- Web: `cd apps/web && npx tsc --noEmit && npx next build`.
- E2E: `cd tests/e2e && npx playwright test` (tự chạy `scripts/e2e_api.sh` → API :8100 DB `anngan_e2e`, web :3100; cần build web trước).
- Dịch vụ cục bộ: `service postgresql start`, `service redis-server start`.
- Sinh lại tài liệu API/ERD: `.venv/bin/python scripts/gen_docs.py`.

## Quy ước mã
- Backend: mỗi module có `models.py`, `service.py` (nghiệp vụ + `ctx.require(perm)` + `audit.record`), `router.py` (commit ở router). Lỗi nghiệp vụ dùng `app.core.errors` (mã lỗi tiếng Anh, thông điệp tiếng Việt). Chuyển trạng thái dự án CHỈ qua `workflows.state_machine.transition`.
- Agent chạy qua `agents.runner.run_agent` với action trong `allowed_actions`. Không cho agent quyền duyệt/xuất bản. Phép tính tài chính/KPI viết code, không dùng LLM.
- Tác vụ nền: `workflows.dispatch.defer()` (gửi sau commit), thân tác vụ ở `workflows/jobs.py`, phải idempotent.
- Dữ liệu nghiệp vụ có `data_mode`; mọi truy vấn lọc theo `ctx.mode`.
- Thay đổi schema: sửa model → `alembic revision --autogenerate` → kiểm tra. Không sửa `migrations/sql/0001_initial_schema.sql`.
- Frontend: trang ở `apps/web/src/app/(studio)/<route>`, dùng `RequirePermission`, `QueryView`, `useAction`, `Can`, `data-testid`; 100% tiếng Việt; component riêng màn hình đặt ở `src/features/<route>`.

## Bẫy đã gặp
- `pkill -f` có thể khớp chính shell đang chạy → kill theo PID.
- Worker Celery phải `import app.db.models` (đã có trong `celery_app.py`) để SQLAlchemy phân giải khoá ngoại.
- Khoá dự án dùng `with_for_update(key_share=True)` (FOR NO KEY UPDATE) để không khoá chéo với bản ghi agent ghi bằng session độc lập.
- Docker daemon không có trong môi trường build hiện tại: chỉ kiểm tra được `docker compose config`.

## Cập nhật tiến độ
Sau mỗi phần việc: chạy test liên quan → cập nhật `docs/architecture/PROJECT_STATUS.md` → commit (nếu được phép).
