# PROJECT STATUS — Ánh Ngân AI Video Studio V2.0

**Cập nhật:** 2026-10-29 · **Giai đoạn hiện tại:** 6 — Verification ✅ hoàn tất · **Nhánh:** `main`

## Chức năng hoàn thành
- 15 màn hình (M01–M15) + trang chi tiết dự án, chi tiết Feedback, tài khoản; sidebar 5 nhóm; trạng thái loading/empty/error/success/không có quyền.
- 12 module backend (B01–B12), 159 endpoint, 45 bảng, 2 migration (DDL + trigger bất biến/append-only).
- 10 AI Agent với Registry, phạm vi quyền, giới hạn, log thực thi; Mock LLM (DEMO) + adapter Claude (PRODUCTION, chưa xác minh bằng key thật).
- Workflow 20 trạng thái; A01 Director tự chạy tới cổng duyệt của con người.
- Video: Mock provider (MP4 thật), nhập Google Flow thủ công, adapter API chính thức; render FFmpeg 1080×1920 + phụ đề + logo + voice-over + nhạc nền + thumbnail; QC tự động (FFprobe, LUFS, khung đen, tuân thủ).
- QC 10 tiêu chí, phê duyệt; Feedback Loop 360° 8 bước + REOPENED; Lessons Learned áp dụng/rollback prompt.
- Publishing (lịch, gói xuất file, URL, chặn DEMO tự đăng), Analytics (thủ công, CSV, insights, export), Dashboard CEO 14 KPI có công thức.
- RBAC 8 vai trò × 55 quyền, CSRF, khoá tài khoản, rate limit, mã hoá secret, audit log, ngân sách + chặn cứng, backup/restore, DEMO/PRODUCTION tách dữ liệu.
- Celery worker + beat (khôi phục tác vụ kẹt), Docker Compose (Postgres, Redis, MinIO, API, worker, beat, web, Nginx, Prometheus), tài liệu đầy đủ, seed dữ liệu mẫu DEMO.

## Kiểm thử (lần chạy cuối 2026-10-29)
| Bộ | Kết quả |
|---|---|
| Ruff (Python lint) | ✅ sạch |
| Pytest unit + integration | ✅ **87/87** (gồm render MP4 thật 540p và 1080p, backup/restore, Celery task registry) |
| TypeScript + `next build` | ✅ |
| Playwright E2E (16 file, 15 màn hình + đăng nhập/shell) | ✅ **31/31** (3,0 phút) |
| npm audit (web, production deps) | ✅ 0 lỗ hổng |
| Celery worker thật (Redis, không eager) | ✅ kiểm chứng thủ công: worker lỗi → `/jobs/recover` → tạo cảnh + render → FINAL_QC |
| Docker | ⚠️ `docker compose config` hợp lệ; **chưa chạy** vì môi trường build không có Docker daemon |

## Lỗi đã phát hiện & đã sửa trong giai đoạn kiểm thử
1. Tạo cảnh khi dự án NEEDS_MANUAL_ACTION bỏ qua kiểm tra tài nguyên → chặn (`ASSET_VALIDATION_REQUIRED`).
2. Retry sau FAILED chạy sai bước → state machine ghi nhớ bước lỗi.
3. A01 Director `refresh()` làm mất thay đổi → viết kịch bản lặp; đã sửa + test hồi quy.
4. Worker thiếu nạp model → lỗi khoá ngoại; đã sửa + test.
5. Bộ lọc tuân thủ bỏ sót "sữa … sơ sinh" → mở rộng quy tắc.
6. Idempotency khi 2 request đồng thời → trả về bản đã có.
7. Dashboard lọc kỳ + ngày theo giờ Việt Nam; xoá API key nhà cung cấp; chặn rò rỉ API key tới host lạ; production từ chối khoá mặc định.

## Chưa hoàn thành / giới hạn đã biết
- Chưa kết nối thật: Claude, Veo/Vertex AI, TTS, Facebook/TikTok/YouTube/Zalo (cần quyền API). Xem `docs/deployment/INTEGRATIONS.md`.
- S3/MinIO adapter chưa chạy với MinIO thật; Docker chưa chạy thật.
- Timeline M06 sắp xếp bằng nút lên/xuống (chưa kéo-thả đa track); chưa có lip-sync tự động (tiêu chí Khẩu hình chấm thủ công).
- Chưa có CSP header cho web; chưa có thông báo Email/Zalo.

## Commit gần nhất
Xem `git log --oneline -5`.

## Công việc tiếp theo (đề xuất)
1. Chạy `docker compose up -d --build` trên máy chủ thật và đi checklist mục D trong INSTALL.md.
2. Cấp key Anthropic → Test ở PRODUCTION → chuyển A02/A08/A09 sang Claude, đặt budget PROVIDER.
3. Xin quyền API Veo (Vertex AI) và cấu hình RealAPIProvider; nghiệm thu với ngân sách nhỏ.
4. Đào tạo người dùng theo `docs/user-guide/HUONG_DAN_SU_DUNG.md`; thay tài khoản DEMO bằng tài khoản thật.
