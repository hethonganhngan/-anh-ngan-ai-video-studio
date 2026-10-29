# ÁNH NGÂN AI VIDEO STUDIO V2.0

Nhà máy sản xuất video AI của **Hệ thống Sữa Ánh Ngân** — kiểm soát chất lượng, chi phí, nhân vật, giọng nói và liên tục cải tiến qua **Feedback Loop 360°**.

> TRAO NIỀM TIN – NHẬN GIÁ TRỊ · AN TÂM CHO MỖI LỰA CHỌN

| Phạm vi | Đã triển khai |
|---|---|
| 15 màn hình | M01 Dashboard CEO · M02 Tạo video · M03 Script & Storyboard · M04 Character & Voice · M05 Production · M06 Editor · M07 QC · M08 Feedback 360° · M09 Lessons Learned · M10 Publishing & Analytics · M11 Dự án & hàng đợi · M12 Thư viện · M13 Kênh & Brand DNA · M14 Agent Control Center · M15 Cài đặt |
| 12 module backend | B01–B12 trong `services/api/app/modules/` |
| 10 AI Agent | A01 Director … A10 Analytics (`services/api/app/agents/`) |
| Workflow | 16 trạng thái chính + FAILED/CANCELLED/RETRY_PENDING/NEEDS_MANUAL_ACTION |
| Video | Mock (MP4 thật bằng FFmpeg), Google Flow nhập thủ công, adapter API chính thức; render MP4 1080×1920 + phụ đề + thumbnail |

## Bắt đầu nhanh

Máy chủ Ubuntu/Debian — cài tự động một lệnh (Docker, khoá bí mật, build, kiểm tra sức khoẻ, lịch backup):
```bash
sudo bash scripts/install_server.sh
```
Mở http://<máy chủ>:8080 — tài khoản Super Admin in ra cuối quá trình cài (lưu tại `var/ADMIN_CREDENTIALS.txt`).

Phát triển (không Docker) — xem [docs/deployment/INSTALL.md](docs/deployment/INSTALL.md):
```bash
scripts/dev_setup.sh
```
```bash
scripts/dev_run.sh
```

Kiểm thử toàn bộ:
```bash
scripts/run_tests.sh
```

## Công nghệ

Next.js 15 · TypeScript · Tailwind 4 · shadcn/ui (Radix) · TanStack Query · React Hook Form · Zod · Recharts — FastAPI · SQLAlchemy 2 · Alembic · Pydantic 2 · PostgreSQL 16 · Redis 7 · Celery 5 — FFmpeg/FFprobe — Docker Compose · Nginx · S3 (tuỳ chọn) · Prometheus — pytest · Playwright.

## Tài liệu

| Tài liệu | Đường dẫn |
|---|---|
| Kiến trúc | [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) |
| Workflow & Feedback Loop | [docs/architecture/WORKFLOW.md](docs/architecture/WORKFLOW.md) |
| Ma trận chức năng | [docs/architecture/FEATURE_MATRIX.md](docs/architecture/FEATURE_MATRIX.md) |
| Tiêu chí nghiệm thu | [docs/architecture/ACCEPTANCE_CRITERIA.md](docs/architecture/ACCEPTANCE_CRITERIA.md) |
| Trạng thái dự án | [docs/architecture/PROJECT_STATUS.md](docs/architecture/PROJECT_STATUS.md) |
| Sổ quyết định | [docs/architecture/DECISION_LOG.md](docs/architecture/DECISION_LOG.md) |
| API (159 endpoint) | [docs/api/ENDPOINTS.md](docs/api/ENDPOINTS.md), `docs/api/openapi.json`, `/docs` |
| Cơ sở dữ liệu (45 bảng) | [docs/database/ERD.md](docs/database/ERD.md) |
| Cài đặt & vận hành | [docs/deployment/INSTALL.md](docs/deployment/INSTALL.md) |
| Tích hợp thật / chưa kết nối | [docs/deployment/INTEGRATIONS.md](docs/deployment/INTEGRATIONS.md) |
| Bảo trì & mở rộng | [docs/deployment/MAINTENANCE.md](docs/deployment/MAINTENANCE.md) |
| Hướng dẫn sử dụng | [docs/user-guide/HUONG_DAN_SU_DUNG.md](docs/user-guide/HUONG_DAN_SU_DUNG.md) |
| Báo cáo nghiệm thu | [docs/architecture/ACCEPTANCE_REPORT.md](docs/architecture/ACCEPTANCE_REPORT.md) |

## Nguyên tắc an toàn

- DEMO MODE không gọi API tính phí, không tự xuất bản; dữ liệu mẫu gắn nhãn DEMO.
- Không giả mạo kết nối: Mock Provider **không phải** AI thật; Google Flow chỉ nhập thủ công; tích hợp chỉ "VERIFIED" khi đã gọi thật bằng quyền hợp lệ.
- Mọi phê duyệt/xuất bản cần con người có quyền; Agent bị giới hạn phạm vi.
- Không tự tạo công dụng sản phẩm; bộ lọc tuân thủ chặn quảng cáo sữa cho trẻ dưới 24 tháng (NĐ 100/2014/NĐ-CP).
