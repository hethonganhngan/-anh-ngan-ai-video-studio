# Chạy thực tế trên máy Windows (không Docker)

Đã kiểm chứng 2026-10-29 trên Windows 11 Pro: 6 dịch vụ chạy, tạo cảnh qua Celery worker, voice-over TTS, render MP4 1080×1920, backup.

## 1. Thành phần

| Dịch vụ | Cách chạy | Cổng |
|---|---|---|
| PostgreSQL 16.13 (portable, bản zip EDB) | `D:\AnhNganStudio\pgsql`, dữ liệu `D:\AnhNganStudio\pgdata` | 5432 (chỉ localhost) |
| Redis 8.10.2 (portable, redis-windows) | `D:\AnhNganStudio\redis` | 6379 (chỉ localhost) |
| API FastAPI | `.venv` + uvicorn | 8000 |
| Celery worker (`--pool threads`, 2 luồng) + beat | `.venv` | — |
| Web Next.js (bản build production) | `node next start` | 3001 |

Dữ liệu lớn nằm ở ổ D (`ANNGAN_DATA_DIR=D:/AnhNganStudio` trong `.env`): `pgdata`, `storage` (media), `backups`, `logs`, `tmp`, `run` (PID).
Python 3.13, Node 22+, FFmpeg đã cài sẵn trên máy. Font phụ đề/thumbnail: `FONT_FILE=C:/Windows/Fonts/arial.ttf`.

## 2. Lệnh vận hành

Chạy trong PowerShell tại thư mục dự án:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\start.ps1
```
```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\status.ps1
```
```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\stop.ps1
```
```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\backup.ps1
```

- `start.ps1` bật theo thứ tự PostgreSQL → Redis → migration → API → worker → beat → web, rồi in kết quả `/health/ready`. Chạy lại khi đã bật thì bỏ qua dịch vụ đang chạy.
- Sau khi sửa mã giao diện: xoá `apps\web\.next\BUILD_ID` (hoặc `npx next build` trong `apps\web`) rồi `stop.ps1` + `start.ps1`.
- Log: `D:\AnhNganStudio\logs\<dịch vụ>.log` và `.err.log`.
- `stop.ps1` chỉ tắt tiến trình theo PID đã lưu, không đụng tới chương trình khác trên máy.

Tự bật khi đăng nhập Windows (tuỳ chọn):
```powershell
schtasks /Create /TN "AnhNganStudio" /SC ONLOGON /TR "powershell -ExecutionPolicy Bypass -WindowStyle Hidden -File C:\ANHNGAN-PROJECTS\anh-ngan-ai-video-studio\scripts\windows\start.ps1"
```
Sao lưu 2h sáng hằng ngày (giữ 14 bản):
```powershell
schtasks /Create /TN "AnhNganStudio-Backup" /SC DAILY /ST 02:00 /TR "powershell -ExecutionPolicy Bypass -File C:\ANHNGAN-PROJECTS\anh-ngan-ai-video-studio\scripts\windows\backup.ps1"
```
Nên chép định kỳ thư mục `D:\AnhNganStudio\backups` sang ổ/máy khác (Google Drive, ổ cứng ngoài).

## 3. Lấy API key (2 key cho 3 dịch vụ)

| Dịch vụ | Key | Nơi lấy | Chi phí tham khảo |
|---|---|---|---|
| Claude — kịch bản, RCA, bài học (A02/A08/A09) | Anthropic API key | console.anthropic.com → Settings → API Keys (nạp credit trước) | Opus 5.5: 4 USD / 20 USD mỗi 1M token vào/ra |
| Gemini Omni Flash — tạo video AI | Gemini API key | aistudio.google.com → Get API key → bật Billing cho project | ~0,10 USD/giây video 720p (không có gói miễn phí) |
| Gemini TTS — giọng đọc tiếng Việt | **cùng key Gemini** | như trên | ~0,00045 USD/giây âm thanh (≈12 đ) |

> Veo 3.1 Preview trên Gemini API đã ngừng ngày 22/10/2026 — Google thay bằng Gemini Omni Flash (`gemini-omni-1.1-flash`).
> Omni chỉ cam kết tiếng Anh, nên mặc định video **không có thoại** (chỉ âm thanh môi trường) và thoại tiếng Việt do Gemini TTS đọc.

**Không gửi key qua chat/email.** Chỉ dán key vào ứng dụng ở M15 — key được mã hoá (Fernet) và chỉ hiện 4 ký tự cuối.

## 4. Bật chạy thật (PRODUCTION)

1. Đăng nhập Super Admin → **M15 Cài đặt → API Connections**:
   - `Anthropic Claude`: dán key → Lưu → bật → **Test** (phải ra VERIFIED; chỉ Test được ở PRODUCTION MODE).
   - `Google Gemini Omni Flash`: dán key Gemini → Lưu → bật → **Test** (đọc thông tin model, không tốn phí).
   - `Google Gemini TTS`: dán cùng key Gemini → Lưu → bật → **Test**.
2. **M15 → Budget**: đặt hạn mức tháng PRODUCTION (mặc định 10.000.000 đ, chặn cứng) và hạn mức theo nhà cung cấp `gemini_omni`.
3. **M15 → chuyển PRODUCTION MODE.** DEMO MODE không bao giờ gọi API tính phí.
4. **M14 Agent Control Center**: đổi A02 (kịch bản), A08, A09 sang provider `anthropic`, model `claude-opus-5-5`.
5. **M04 → Giọng nói mới**: Provider = *Gemini TTS*, chọn giọng (Kore, Aoede, Leda… — nghe thử tại AI Studio), Accent/Chất giọng/Tốc độ dùng làm hướng dẫn đọc, Consent = *Đã đồng ý* (giọng AI dựng sẵn), ghi phạm vi sử dụng. (Voice Lock cần file audio tham chiếu — với giọng AI có thể bỏ qua, hệ thống chỉ cảnh báo.)
6. **M02 Tạo video**: chọn kênh và Voice Profile vừa tạo; khi tạo cảnh chọn nhà cung cấp video *Google Gemini Omni Flash*.
7. **M06 Editor → Tạo giọng đọc AI** → kiểm tra → **Export MP4** → M07 QC.
8. Thử 1 video 16 giây trước (~1,6 USD video + vài trăm đồng giọng đọc) rồi mới chạy hàng loạt.
9. Tắt/xoá tài khoản DEMO (`@anhngan.local`) ở M15 trước khi giao cho nhân viên; tạo tài khoản thật theo vai trò.

## 5. Khắc phục sự cố

| Hiện tượng | Xử lý |
|---|---|
| `status.ps1` báo worker LỖI ngay sau khi bật | Đợi 10–20 giây (worker đang khởi động) rồi chạy lại |
| Web không lên, log `EADDRINUSE 3001` | Cổng bị chiếm — đặt `WEB_PORT=3002` trong `.env` và thêm `http://localhost:3002` vào `CORS_ORIGINS` |
| Cảnh treo ở RUNNING | Beat tự gọi `recover_stuck_jobs` mỗi 5 phút; xem `worker.err.log` |
| Gemini `AUTH_FAILED` | Key sai hoặc project chưa bật Billing |
| Gemini `RATE_LIMITED` | Tự thử lại; giảm số cảnh chạy song song |
| Ổ C đầy | Dữ liệu đã ở ổ D; xoá `%LOCALAPPDATA%\npm-cache`, `%TEMP%` |
