#!/usr/bin/env bash
# =====================================================================
#  Ánh Ngân AI Video Studio — cài đặt tự động trên máy chủ Ubuntu/Debian
#  Dùng:  sudo bash scripts/install_server.sh            (chạy trong thư mục repo đã clone)
#  Tuỳ chọn biến môi trường:
#    ADMIN_EMAIL=ceo@anhngan.vn  HTTP_PORT=8080  WITH_DEMO=1 (tạo user + dữ liệu DEMO)
#    SKIP_CRON=1 (không cài lịch sao lưu hằng ngày)
#  Script: cài Docker (nếu chưa có) → tạo .env với khoá ngẫu nhiên → build & chạy → kiểm tra sức khoẻ
#  → in mật khẩu Super Admin khởi tạo (chỉ hiện 1 lần, lưu tại var/ADMIN_CREDENTIALS.txt quyền 600).
# =====================================================================
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
ADMIN_EMAIL="${ADMIN_EMAIL:-ceo@anhngan.vn}"
HTTP_PORT="${HTTP_PORT:-8080}"
WITH_DEMO="${WITH_DEMO:-0}"
log() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
die() { printf '\n\033[1;31m[LỖI] %s\033[0m\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "Cần chạy bằng quyền root: sudo bash scripts/install_server.sh"
[ -f docker-compose.yml ] || die "Không thấy docker-compose.yml — hãy chạy trong thư mục repo"

# 1. Kiểm tra tài nguyên
log "Kiểm tra máy chủ"
CPU=$(nproc); MEM_GB=$(awk '/MemTotal/ {printf "%d", $2/1024/1024}' /proc/meminfo); DISK_GB=$(df -BG --output=avail "$ROOT" | tail -1 | tr -dc 0-9)
echo "CPU: ${CPU} · RAM: ${MEM_GB} GB · Đĩa trống: ${DISK_GB} GB"
[ "$MEM_GB" -ge 3 ] || die "Cần tối thiểu 4 GB RAM (khuyến nghị 8 GB)"
[ "$DISK_GB" -ge 15 ] || die "Cần tối thiểu 20 GB đĩa trống (khuyến nghị 50 GB)"

# 2. Cài Docker Engine + Compose plugin (repo chính thức của Docker)
if ! command -v docker >/dev/null 2>&1; then
  log "Cài Docker Engine"
  . /etc/os-release
  case "$ID" in ubuntu|debian) ;; *) die "Script hỗ trợ Ubuntu/Debian. Hệ điều hành khác: cài Docker theo https://docs.docker.com/engine/install/";; esac
  apt-get update -qq
  apt-get install -y -qq ca-certificates curl gnupg openssl
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL "https://download.docker.com/linux/${ID}/gpg" -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/${ID} ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -qq
  apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
else
  log "Docker đã có: $(docker --version)"
fi
docker compose version >/dev/null 2>&1 || die "Thiếu docker compose plugin (apt-get install docker-compose-plugin)"
docker info >/dev/null 2>&1 || die "Docker daemon chưa chạy (systemctl start docker)"

# 3. Tạo .env với khoá ngẫu nhiên (không ghi đè .env đã có)
rand() { openssl rand -base64 48 | tr -dc 'A-Za-z0-9' | head -c "${1:-40}"; }
if [ -f .env ]; then
  log ".env đã tồn tại — giữ nguyên (không ghi đè)"
else
  log "Tạo .env với khoá bí mật ngẫu nhiên"
  ADMIN_PWD="$(rand 14)Aa1"
  FERNET=$(openssl rand -base64 32 | tr '+/' '-_')
  cp .env.example .env
  sed -i \
    -e "s|^SECRET_KEY=.*|SECRET_KEY=$(rand 64)|" \
    -e "s|^ENCRYPTION_KEY=.*|ENCRYPTION_KEY=${FERNET}|" \
    -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(rand 32)|" \
    -e "s|^MINIO_ROOT_PASSWORD=.*|MINIO_ROOT_PASSWORD=$(rand 32)|" \
    -e "s|^INITIAL_ADMIN_EMAIL=.*|INITIAL_ADMIN_EMAIL=${ADMIN_EMAIL}|" \
    -e "s|^INITIAL_ADMIN_PASSWORD=.*|INITIAL_ADMIN_PASSWORD=${ADMIN_PWD}|" \
    -e "s|^HTTP_PORT=.*|HTTP_PORT=${HTTP_PORT}|" \
    -e "s|^CORS_ORIGINS=.*|CORS_ORIGINS=http://localhost:${HTTP_PORT}|" \
    .env
  if [ "$WITH_DEMO" = "1" ]; then
    sed -i -e "s|^DEMO_USER_PASSWORD=.*|DEMO_USER_PASSWORD=$(rand 14)Aa1|" -e "s|^SEED_ARGS=.*|SEED_ARGS=--demo-data|" .env
  else
    sed -i -e "s|^SEED_ARGS=.*|SEED_ARGS=--no-demo-users|" .env
  fi
  chmod 600 .env
  mkdir -p var
  { echo "Ánh Ngân AI Video Studio — tài khoản khởi tạo ($(date -Iseconds))"
    echo "URL:      http://<địa-chỉ-máy-chủ>:${HTTP_PORT}"
    echo "Email:    ${ADMIN_EMAIL}"
    echo "Mật khẩu: ${ADMIN_PWD}"
    echo "Đổi mật khẩu ngay sau lần đăng nhập đầu, rồi xoá file này."; } > var/ADMIN_CREDENTIALS.txt
  chmod 600 var/ADMIN_CREDENTIALS.txt
fi

# 4. Build & chạy
log "Build image và khởi động (lần đầu 5–15 phút)"
docker compose build
docker compose up -d

# 5. Chờ sẵn sàng
log "Chờ hệ thống sẵn sàng"
for i in $(seq 1 90); do
  if curl -fs "http://localhost:${HTTP_PORT}/health/ready" -o /tmp/anngan_ready.json 2>/dev/null; then break; fi
  sleep 5
done
curl -fs "http://localhost:${HTTP_PORT}/health/ready" >/dev/null || { docker compose ps; docker compose logs --tail 50 migrate api; die "Hệ thống chưa sẵn sàng — xem log phía trên"; }
docker compose ps --format 'table {{.Service}}\t{{.State}}\t{{.Status}}'
curl -s "http://localhost:${HTTP_PORT}/health/ready"; echo

# 6. Sao lưu tự động hằng ngày 2h sáng (pg_dump trong container api, giữ 14 bản)
if [ "${SKIP_CRON:-0}" = "1" ]; then
  log "Bỏ qua cài lịch sao lưu (SKIP_CRON=1)"
else
log "Cài lịch sao lưu hằng ngày"
cat > /etc/cron.d/anngan-backup <<CRON
0 2 * * * root cd ${ROOT} && docker compose exec -T api python -c "from app.modules.administration.backup import create_backup; print(create_backup())" >> /var/log/anngan-backup.log 2>&1
CRON
fi

log "HOÀN TẤT"
echo "Mở: http://<địa-chỉ-máy-chủ>:${HTTP_PORT}"
[ -f var/ADMIN_CREDENTIALS.txt ] && cat var/ADMIN_CREDENTIALS.txt
echo "Bật HTTPS (khuyến nghị): đặt reverse proxy/Cloudflare Tunnel phía trước cổng ${HTTP_PORT} và COOKIE_SECURE=true trong .env"
