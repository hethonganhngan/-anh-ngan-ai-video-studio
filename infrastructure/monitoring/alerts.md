# Cảnh báo vận hành đề xuất

| Cảnh báo | Điều kiện (PromQL / kiểm tra) | Hành động |
|---|---|---|
| API lỗi 5xx | `sum(rate(anngan_http_requests_total{status=~"5.."}[5m])) > 0.1` | Xem log `api`, `docker compose logs api` |
| API chậm | `histogram_quantile(0.95, rate(anngan_http_request_seconds_bucket[5m])) > 2` | Kiểm tra DB/Redis |
| Worker không chạy | `GET /health/ready` → `checks.worker.ok=false` | `docker compose restart worker` |
| Hàng đợi kẹt | M11 → Hàng đợi có job QUEUED > 10 phút | Bấm "Khôi phục tác vụ kẹt" (beat tự chạy mỗi 5 phút) |
| Ngân sách | Dashboard CEO → Cảnh báo ngân sách ≥ 80% | Điều chỉnh tại M15 → Budget |
| Backup | Không có file backup mới trong 24h | Chạy `scripts/backup.sh` / M15 → Backup |
