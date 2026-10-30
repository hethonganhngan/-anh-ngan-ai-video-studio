# PROJECT STATUS — Ánh Ngân AI Video Studio V2.0

**Cập nhật:** 2026-10-30 · **Giai đoạn hiện tại:** 6 — Verification ✅ hoàn tất · Triển khai Docker tự động ✅ · Chạy thật trên Windows (Veo/Vertex AI) · **Nhánh:** `windows-production-ai`

## Chức năng hoàn thành
- 15 màn hình (M01–M15) + trang chi tiết dự án, chi tiết Feedback, tài khoản; sidebar 5 nhóm; trạng thái loading/empty/error/success/không có quyền.
- 12 module backend (B01–B12), 159 endpoint, 45 bảng, 2 migration (DDL + trigger bất biến/append-only).
- 10 AI Agent với Registry, phạm vi quyền, giới hạn, log thực thi; Mock LLM (DEMO) + adapter Claude (PRODUCTION, chưa xác minh bằng key thật).
- Workflow 20 trạng thái; A01 Director tự chạy tới cổng duyệt của con người.
- Video: Mock provider (MP4 thật), nhập Google Flow thủ công, adapter API chính thức; render FFmpeg 1080×1920 + phụ đề + logo + voice-over + nhạc nền + thumbnail; QC tự động (FFprobe, LUFS, khung đen, tuân thủ).
- QC 10 tiêu chí, phê duyệt; Feedback Loop 360° 8 bước + REOPENED; Lessons Learned áp dụng/rollback prompt.
- Publishing (lịch, gói xuất file, URL, chặn DEMO tự đăng), Analytics (thủ công, CSV, insights, export), Dashboard CEO 14 KPI có công thức.
- RBAC 8 vai trò × 55 quyền, CSRF, khoá tài khoản, rate limit, mã hoá secret, audit log, ngân sách + chặn cứng, backup/restore, DEMO/PRODUCTION tách dữ liệu.
- Celery worker + beat (khôi phục tác vụ kẹt), Docker Compose (Postgres, Redis, API, worker, beat, web, Nginx, Prometheus) + script cài đặt tự động `scripts/install_server.sh` (đã chạy thật: 7 dịch vụ healthy), tài liệu đầy đủ, seed dữ liệu mẫu DEMO.

- **Chế độ AUTO trọn gói (2026-10-30, D19/D20):** M02 nhập chủ đề → A01 viết kịch bản → tự duyệt nếu sạch (vi phạm CRITICAL thì dừng) → Veo trên Vertex AI tạo cảnh (ảnh Character Lock làm tham chiếu, cấm chữ/logo, không tiếng nói) → QC kỹ thuật → tự lồng giọng Voice Profile M04 → dựng có logo + phụ đề → dừng ở FINAL_QC. M05 có nút "Tạo trên Flow" (sao prompt + mở Google Flow) và đổi nhà cung cấp video của dự án.

- **Flow tự động qua Chrome CDP (2026-10-30, D21, thử nghiệm):** provider `flow_cdp` (0đ, dùng lượt gói Google). Chạy `scripts/windows/start-flow-chrome.ps1`, đăng nhập Flow 1 lần, M15 → bật + Kiểm tra. M02 tự chọn provider thật rẻ nhất. Chạy thật PRJ-2610-0011 (đã kiểm chứng trên Flow thật): mỗi cảnh mở **phiên tác nhân mới**, gắn chip `@Mẹ Ánh Ngân` + `@Cửa hàng Ánh Ngân.jpg`, theo dõi ô đầu lưới (hiện % khi đang tạo) rồi mở ô đó → Tải xuống 720p gốc; tiếng gốc Flow = 0, chỉ giọng M04 (D21). Sửa lỗi có sẵn: nhập/tạo lại cảnh sau khi đã dựng thì timeline cũ giữ clip cũ → nay tự đồng bộ (`sync_timeline_clips`). Cần Playwright ≥1.64. Không tự tạo nội dung khác trong dự án Flow khi app đang tạo (app lấy ô mới nhất). Flow gắn hình mờ ✦ góc phải dưới.

- **Giọng chính chủ VieNeu (2026-10-30, D23):** provider TTS `vieneu_local` (M04: "Giọng nhân bản từ bản ghi âm"), `scripts/windows/start-vieneu.ps1` cài/chạy VieNeu-TTS v3.8.3 (CPU), start/stop.ps1 tự bật/tắt nếu đã cài. Chưa cài/chạy thật trên máy (cần người dùng cho phép cài mã bên ngoài).
- **Lưu ý prompt M05 (2026-10-30, D24):** A02.script v2 + A03.scene_prompt v2 đã kích hoạt ở PRODUCTION (quy tắc thoại tự nhiên, khối nhận diện, chống lộ AI); `to_flow_prompt` giữ nguyên ngoại hình + trang phục và các dòng "Lưu ý". Seed mới cũng mang các quy tắc này.

## Kiểm thử (lần chạy cuối 2026-10-29)
| Bộ | Kết quả |
|---|---|
| Ruff (Python lint) | ✅ sạch |
| Pytest unit + integration | ✅ **87/87** (gồm render MP4 thật 540p và 1080p, backup/restore, Celery task registry) |
| TypeScript + `next build` | ✅ |
| Playwright E2E (16 file, 15 màn hình + đăng nhập/shell) | ✅ **31/31** (3,0 phút) |
| npm audit (web, production deps) | ✅ 0 lỗ hổng |
| Celery worker thật (Redis, không eager) | ✅ kiểm chứng thủ công: worker lỗi → `/jobs/recover` → tạo cảnh + render → FINAL_QC |
| Docker | ✅ Cài tự động + chạy thật: 7 dịch vụ healthy, tạo video 1080p qua worker trong container, backup (image backend kiểm thử trên nền Ubuntu do mạng kiểm thử chặn kho Debian) |

## Lỗi đã phát hiện & đã sửa trong giai đoạn kiểm thử
1. Tạo cảnh khi dự án NEEDS_MANUAL_ACTION bỏ qua kiểm tra tài nguyên → chặn (`ASSET_VALIDATION_REQUIRED`).
2. Retry sau FAILED chạy sai bước → state machine ghi nhớ bước lỗi.
3. A01 Director `refresh()` làm mất thay đổi → viết kịch bản lặp; đã sửa + test hồi quy.
4. Worker thiếu nạp model → lỗi khoá ngoại; đã sửa + test.
5. Bộ lọc tuân thủ bỏ sót "sữa … sơ sinh" → mở rộng quy tắc.
6. Idempotency khi 2 request đồng thời → trả về bản đã có.
7. Dashboard lọc kỳ + ngày theo giờ Việt Nam; xoá API key nhà cung cấp; chặn rò rỉ API key tới host lạ; production từ chối khoá mặc định.

## Chưa hoàn thành / giới hạn đã biết
- 2026-10-30 (Windows): pytest 117/118 — `test_production_refuses_default_secrets` lỗi do máy đọc `.env` thật (không liên quan mã). Chưa xác minh: `veo-3.1-fast-generate-001` có nhận `referenceImages` không (nếu 400 → đổi model Veo 3.1 thường ở M15); hạn mức Gemini TTS (lỗi lồng tiếng ghi vào `last_error`, video vẫn dựng).
- Adapter mới (2026-10-29, chưa xác minh bằng key thật): Gemini LLM (A02/A08/A09, mặc định), Gemini Omni Flash (video), Gemini TTS (voice-over M06) — toàn bộ AI chỉ cần 1 key Gemini. Chạy thực tế trên Windows không Docker: `docs/deployment/WINDOWS.md` (pytest 101/101 trên Windows).
- Chưa kết nối thật: Gemini LLM, Gemini Omni, Gemini TTS, Claude (tuỳ chọn), Veo/Vertex AI, Facebook/TikTok/YouTube/Zalo (cần quyền API). Xem `docs/deployment/INTEGRATIONS.md`.
- S3 adapter chưa chạy với S3 thật (mặc định dùng volume). Build `api.Dockerfile` nền Debian cần quan sát lần đầu trên máy chủ thật.
- Timeline M06 sắp xếp bằng nút lên/xuống (chưa kéo-thả đa track); chưa có lip-sync tự động (tiêu chí Khẩu hình chấm thủ công).
- Chưa có CSP header cho web; chưa có thông báo Email/Zalo.

## Commit gần nhất
Xem `git log --oneline -5`.

## Công việc tiếp theo (đề xuất)
1. Trên máy chủ thật: `sudo bash scripts/install_server.sh` rồi đi checklist mục D trong INSTALL.md.
2. Cấp key Anthropic → Test ở PRODUCTION → chuyển A02/A08/A09 sang Claude, đặt budget PROVIDER.
3. Xin quyền API Veo (Vertex AI) và cấu hình RealAPIProvider; nghiệm thu với ngân sách nhỏ.
4. Đào tạo người dùng theo `docs/user-guide/HUONG_DAN_SU_DUNG.md`; thay tài khoản DEMO bằng tài khoản thật.
