# Cài đặt & vận hành

## A. Cài đặt tự động một lệnh (khuyến nghị — Ubuntu 22.04/24.04, Debian 12)

Yêu cầu máy chủ: 4 vCPU, 8 GB RAM (tối thiểu 4 GB), 50 GB đĩa (tối thiểu 20 GB), quyền root.

```bash
git clone https://github.com/hethonganhngan/-anh-ngan-ai-video-studio.git anngan-studio
```
```bash
cd anngan-studio && sudo ADMIN_EMAIL=ceo@anhngan.vn bash scripts/install_server.sh
```

Script `scripts/install_server.sh` tự động:
1. Kiểm tra CPU/RAM/đĩa.
2. Cài Docker Engine + Compose từ kho chính thức của Docker (nếu chưa có).
3. Tạo `.env` với khoá bí mật ngẫu nhiên (SECRET_KEY, ENCRYPTION_KEY, mật khẩu DB, mật khẩu Super Admin) — không ghi đè `.env` đã có.
4. Build image và khởi động 7 dịch vụ: `postgres`, `redis`, `migrate` (alembic + seed, chạy 1 lần), `api`, `worker`, `beat`, `web`, `gateway` (Nginx).
5. Chờ `/health/ready` đạt, in bảng trạng thái.
6. Cài lịch sao lưu 2h sáng hằng ngày (`/etc/cron.d/anngan-backup`).
7. In URL + email + mật khẩu Super Admin (lưu tại `var/ADMIN_CREDENTIALS.txt`, quyền 600 — đổi mật khẩu ngay, rồi xoá file).

Tuỳ chọn: `HTTP_PORT=8080`, `WITH_DEMO=1` (tài khoản + dữ liệu mẫu DEMO), `SKIP_CRON=1`, `SKIP_BUILD=1` (dùng image đã build sẵn).

Lưu trữ media: mặc định trên volume Docker `backend_var` dùng chung giữa API và worker. Dùng S3-compatible (AWS S3, Cloudflare R2, Wasabi): đặt `STORAGE_BACKEND=s3` và `S3_*` trong `.env`. (MinIO đã ngừng phát hành image công khai trên Docker Hub nên không còn đi kèm.)

HTTPS: đặt Nginx/Caddy/Cloudflare Tunnel phía trước cổng gateway, đặt `COOKIE_SECURE=true`.
Giám sát: `docker compose --profile monitoring up -d prometheus`.

Lệnh vận hành thường dùng:
```bash
docker compose ps
```
```bash
docker compose logs -f api worker
```
```bash
git pull && docker compose up -d --build
```

> **Kết quả kiểm chứng (2026-10-29):** chạy `install_server.sh` trên bản clone sạch: 7 dịch vụ healthy, `/health/ready` ok, đăng nhập qua gateway, tạo video → worker Celery trong container render MP4 1080×1920 trong 15 giây, tải video qua gateway, backup pg_dump trong container. Image **web** build từ Dockerfile thật. Image **backend** trong môi trường kiểm thử phải dựng trên nền Ubuntu vì mạng kiểm thử chặn kho gói Debian (`deb.debian.org`); trên máy chủ thật dùng nguyên `api.Dockerfile` (nền python:3.13-slim) — lần build đầu trên máy chủ thật là bước cần quan sát.

## B. Chạy phát triển (không Docker)

Yêu cầu: Python 3.13, Node 22, PostgreSQL 16, Redis 7, FFmpeg 6+ (có libass), font DejaVu.

Ubuntu/Debian:
```bash
sudo apt-get install -y postgresql redis-server ffmpeg fonts-dejavu-core
```
macOS:
```bash
brew install postgresql@16 redis ffmpeg
```
Tạo DB:
```bash
sudo -u postgres psql -c "CREATE ROLE anngan LOGIN PASSWORD 'anngan' CREATEDB;" -c "CREATE DATABASE anngan_studio OWNER anngan;"
```
```bash
scripts/dev_setup.sh
```
```bash
scripts/dev_run.sh
```
Web: http://localhost:3000 · API docs: http://localhost:8000/docs. Không có worker: đặt `CELERY_TASK_ALWAYS_EAGER=true` (tác vụ chạy đồng bộ trong API — chỉ dùng phát triển).

## C. Kiểm thử

```bash
scripts/run_tests.sh
```
Gồm: ruff, pytest (unit + integration trên DB `anngan_test`, render MP4 thật cả 1080p), typecheck + build web, Playwright E2E 15 màn hình (tự dựng API trên DB `anngan_e2e` port 8100 + web port 3100). Cần tạo trước DB `anngan_test`, `anngan_e2e` thuộc user `anngan`.

## D. Kiểm tra sau triển khai (checklist)

- [ ] `GET /health/ready` trả `status: ok`, `worker.ok: true`
- [ ] Đăng nhập Super Admin, đổi mật khẩu khởi tạo
- [ ] M15 → System Health: database, redis, ffmpeg, storage, worker đều xanh
- [ ] M15 → tạo tài khoản thật theo vai trò; tắt/xoá tài khoản DEMO nếu đã seed
- [ ] M15 → Budget: đặt hạn mức tháng cho DEMO và PRODUCTION
- [ ] M02 tạo 1 video DEMO 16s → tới FINAL_QC, xem MP4 tại M07
- [ ] M15 → Backup: tạo bản sao lưu đầu tiên; cấu hình cron `scripts/backup.sh`

## E. Sao lưu & khôi phục

- Tự động: cron `0 2 * * * /opt/anngan/scripts/backup.sh` (pg_dump `-Fc` + nén media local; giữ 14 bản).
- Docker: `docker compose exec api python -c "from app.modules.administration.backup import create_backup; print(create_backup())"`; sao chép thêm volume `backend_var` (media) sang ổ/máy khác định kỳ.
- Khôi phục: M15 → Backup → chọn file → gõ `RESTORE <tên file>` (chỉ Super Admin). Hành động được ghi audit log.

## F. Tài khoản khởi tạo an toàn

- Super Admin: `INITIAL_ADMIN_EMAIL`; mật khẩu từ `INITIAL_ADMIN_PASSWORD` hoặc sinh ngẫu nhiên (in một lần, cờ `must_change_password`).
- Tài khoản DEMO (pm, sysadmin, creator, editor, qc, publisher, viewer `@anhngan.local`) chỉ tạo khi không có `--no-demo-users`, mật khẩu `DEMO_USER_PASSWORD` hoặc ngẫu nhiên.
- Chính sách mật khẩu: ≥ 10 ký tự, có chữ hoa, chữ thường, số; khoá 15 phút sau 5 lần sai.
