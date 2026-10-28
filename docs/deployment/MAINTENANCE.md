# Bảo trì & mở rộng

## Vận hành định kỳ
| Tần suất | Việc | Nơi làm |
|---|---|---|
| Hằng ngày | Xem cảnh báo ngân sách, hàng đợi kẹt, Feedback P0 | M01, M11, M08 |
| Hằng ngày | Backup tự động (cron) | `scripts/backup.sh` |
| Hằng tuần | Rà Agent lỗi/latency, chi phí theo provider | M14, M15 |
| Hằng tuần | Duyệt bài học chờ duyệt, CAPA quá hạn | M09, M08 |
| Hằng tháng | Kiểm tra khôi phục backup trên máy thử; xoay vòng mật khẩu/API key | M15 |
| Khi nâng cấp | `docker compose pull && docker compose up -d --build` (migrate tự chạy) | — |

## Thêm/sửa cấu trúc dữ liệu
1. Sửa model trong `services/api/app/modules/<module>/models.py`.
2. `cd services/api && ../../.venv/bin/alembic revision --autogenerate -m "mô tả"` → kiểm tra file sinh ra.
3. `alembic upgrade head` và chạy `pytest`. **Không sửa** `migrations/sql/0001_initial_schema.sql`.

## Thêm nhà cung cấp video thật
1. Đọc tài liệu API chính thức của nhà cung cấp; xác định endpoint submit/status/result.
2. M15 → API Connections: thêm/sửa bản ghi `provider_type=VIDEO` (ví dụ `veo_vertex`), điền `config` theo mẫu trong `app/providers/video/real_api.py`, nhập API key (mã hoá), đặt `unit_cost` (VND/giây).
3. Nếu API cần SDK riêng: tạo lớp con `VideoProvider` mới trong `app/providers/video/` và đăng ký ở `registry.py`.
4. Chuyển PRODUCTION, tạo 1 dự án thử với ngân sách nhỏ, xác nhận job SUCCEEDED rồi mới đánh dấu VERIFIED.

## Kết nối Claude cho Agent
M15 → API Connections → Anthropic: nhập key, bật, Test (PRODUCTION). M14 → A02/A08/A09 → provider `anthropic`, model `claude-opus-5-5` (hoặc sonnet/haiku để tiết kiệm). Theo dõi token/chi phí tại M14; đặt `max_cost_per_run` và budget PROVIDER `anthropic`.

## Thêm màn hình / quyền
- Quyền mới: thêm vào `app/core/permissions.py` (PERMISSIONS + ROLES) → chạy lại seed (đồng bộ vai trò).
- Màn hình mới: `apps/web/src/app/(studio)/<route>/page.tsx`, thêm vào `lib/nav.ts`, dùng `RequirePermission`, `QueryView`, `useAction`.

## Xử lý sự cố nhanh
| Triệu chứng | Kiểm tra | Cách xử lý |
|---|---|---|
| Job đứng QUEUED | `/health/ready` worker | Khởi động lại worker, M11 → "Khôi phục tác vụ kẹt" |
| Render FAILED | M11 → chi tiết dự án → log render | Sửa timeline/asset, bấm Retry |
| Bị chặn ngân sách | M01 cảnh báo, M15 Budget | Tăng hạn mức (có audit) hoặc giảm số cảnh |
| Không đăng nhập được | Khoá 15 phút sau 5 lần sai | Admin mở lại tại M15 hoặc chờ |
| Video không phát trên web | Cookie khác domain | Dùng gateway cùng origin (docker-compose) |
