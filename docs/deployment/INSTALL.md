# Cài đặt & vận hành

## A. Docker Compose (khuyến nghị cho máy chủ cửa hàng / VPS)

Yêu cầu: Docker Engine 24+ và Docker Compose v2, 4 vCPU, 8 GB RAM, 50 GB đĩa.

```bash
cp .env.example .env
```
Sửa `.env`: `SECRET_KEY`, `ENCRYPTION_KEY`, `POSTGRES_PASSWORD`, `MINIO_ROOT_PASSWORD`, `INITIAL_ADMIN_EMAIL`. Để trống `INITIAL_ADMIN_PASSWORD` để hệ thống tự sinh mật khẩu mạnh. Môi trường thật: `SEED_ARGS=--no-demo-users`, `COOKIE_SECURE=true` khi có HTTPS.

```bash
docker compose up -d --build
```
```bash
docker compose logs migrate
```
Lệnh trên in **mật khẩu Super Admin khởi tạo (chỉ một lần)** — lưu vào nơi an toàn; hệ thống bắt buộc đổi ở lần đăng nhập đầu. Mở `http://<máy chủ>:8080`.

Dịch vụ: `postgres`, `redis`, `minio` (console `127.0.0.1:9001`), `migrate` (alembic + seed, chạy 1 lần), `api`, `worker` (generation/render), `beat` (khôi phục tác vụ kẹt 5 phút/lần), `web`, `gateway` (Nginx cùng origin). Giám sát: `docker compose --profile monitoring up -d prometheus`.

HTTPS: đặt Nginx/Caddy/Cloudflare Tunnel phía trước gateway, đặt `COOKIE_SECURE=true`.

> Môi trường build hiện tại không có Docker daemon nên compose mới được kiểm tra cú pháp (`docker compose config`); các thành phần đã chạy thật bằng dịch vụ cục bộ tương đương (PostgreSQL 16, Redis 7, Celery worker, FFmpeg). Lần đầu triển khai Docker hãy chạy kiểm tra ở mục D.

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
- Docker: `docker compose exec api python -c "from app.modules.administration.backup import create_backup; print(create_backup())"`; MinIO dùng `mc mirror` sang ổ khác.
- Khôi phục: M15 → Backup → chọn file → gõ `RESTORE <tên file>` (chỉ Super Admin). Hành động được ghi audit log.

## F. Tài khoản khởi tạo an toàn

- Super Admin: `INITIAL_ADMIN_EMAIL`; mật khẩu từ `INITIAL_ADMIN_PASSWORD` hoặc sinh ngẫu nhiên (in một lần, cờ `must_change_password`).
- Tài khoản DEMO (pm, sysadmin, creator, editor, qc, publisher, viewer `@anhngan.local`) chỉ tạo khi không có `--no-demo-users`, mật khẩu `DEMO_USER_PASSWORD` hoặc ngẫu nhiên.
- Chính sách mật khẩu: ≥ 10 ký tự, có chữ hoa, chữ thường, số; khoá 15 phút sau 5 lần sai.
