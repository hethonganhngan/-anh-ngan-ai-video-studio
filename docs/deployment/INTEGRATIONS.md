# Danh sách tích hợp: thật / chưa kết nối

| Tích hợp | Trạng thái | Đã kiểm thử | Ghi chú |
|---|---|---|---|
| PostgreSQL 16 | ✅ Thật | ✅ pytest + E2E | Trigger bất biến + audit append-only |
| Redis 7 + Celery | ✅ Thật | ✅ chạy worker thật, khôi phục sau lỗi worker | Broker, rate limit |
| FFmpeg / FFprobe | ✅ Thật | ✅ render MP4 540p & 1080p, đo LUFS, khung đen | Phụ đề libass, font DejaVu |
| Object Storage local | ✅ Thật | ✅ | Mặc định dev/test |
| Docker Compose (7 dịch vụ) | ✅ Thật | ✅ cài tự động + tạo video + backup trong container | Xem INSTALL.md mục A |
| Object Storage volume (mặc định Docker) | ✅ Thật | ✅ | Volume `backend_var` dùng chung API + worker |
| Object Storage S3-compatible | ⚠️ Đã viết adapter (boto3) | ❌ chưa chạy với S3 thật | Bật bằng `STORAGE_BACKEND=s3` + `S3_*` |
| MockVideoProvider | ✅ (giả lập, **không phải AI**) | ✅ | Chỉ DEMO, chi phí mô phỏng |
| Google Flow | ✅ Nhập thủ công | ✅ upload hợp lệ / từ chối sai tỉ lệ, file giả | Flow **không có API công khai** — không tự động hoá |
| Google Gemini Omni Flash (thay Veo 3.1 Preview, ngừng 22/10/2026) | ⚠️ Adapter `gemini_omni` (Interactions API, chạy nền + dự phòng đồng bộ) | ✅ unit test giả lập HTTP; ❌ chưa gọi bằng key thật | M15 → `gemini_omni` → key Gemini → Test (đọc model, không tốn phí). Video không thoại; thoại do TTS |
| Google Veo (Vertex AI) / API video khác | ❌ Chưa kết nối | ❌ | `RealAPIProvider` cấu hình được; cần key + xác minh. Không tính là kết nối thật |
| Google Gemini LLM (A02, A08, A09 — mặc định) | ⚠️ Adapter `gemini_llm` (Interactions API, structured output) | ✅ unit test giả lập HTTP; ❌ chưa gọi bằng key thật | Dùng chung key Gemini; M15 → Test → PRODUCTION; model chọn tại M14 |
| Anthropic Claude (A02, A08, A09) | ❌ Chưa kết nối | ⚠️ Adapter theo SDK chính thức, chưa gọi bằng key thật | M15 → API Connections → nhập key → bật → Test (ở PRODUCTION) → đổi provider agent tại M14 |
| Gemini TTS (giọng đọc tiếng Việt) | ⚠️ Adapter `gemini_tts` + M06 “Tạo giọng đọc AI” | ✅ unit test giả lập HTTP + integration DEMO (Mock TTS); ❌ chưa gọi bằng key thật | Dùng chung key Gemini; Voice Profile chọn provider Gemini TTS + tên giọng. Vẫn hỗ trợ file thu âm có consent |
| Facebook Pages / TikTok / YouTube / Zalo OA | ❌ Chưa kết nối | ✅ chặn đúng khi chưa có quyền | Dùng chế độ **Xuất file + cập nhật thủ công** (đã kiểm thử) |
| Email/Zalo thông báo | ❌ | ❌ | Thông báo trong ứng dụng hoạt động |

Quy tắc: chỉ đánh dấu `VERIFIED` khi gọi API thật thành công bằng quyền hợp lệ. DEMO MODE không gọi API tính phí và không tự xuất bản.
