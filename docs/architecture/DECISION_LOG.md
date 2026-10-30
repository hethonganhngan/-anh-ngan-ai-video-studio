# Sổ quyết định kiến trúc (ADR)

| # | Ngày | Quyết định | Lý do | Phương án đã cân nhắc |
|---|---|---|---|---|
| D01 | 2026-10-28 | Modular Monolith + Celery worker | Đúng Master Prompt; một codebase dễ vận hành cho chuỗi bán lẻ; tách tác vụ nặng ra worker | Microservices (quá phức tạp giai đoạn đầu) |
| D02 | 2026-10-28 | Kênh & Brand DNA thuộc B01 Project Manager; Thư viện tài nguyên là hạ tầng `app/media` | Giữ đúng 12 module nghiệp vụ; tài nguyên phục vụ mọi module | Tạo module thứ 13 (vi phạm phạm vi) |
| D03 | 2026-10-28 | `app` của API và worker là namespace package | Giữ đúng cấu trúc thư mục `services/api/app` và `services/worker/app`, worker dùng chung mã nghiệp vụ | Đổi tên package worker (lệch cấu trúc) |
| D04 | 2026-10-28 | Migration 0001 dùng DDL đóng băng sinh từ metadata | Autogenerate sắp xếp sai bảng có khoá ngoại vòng; DDL đóng băng tái lập chính xác, migration sau dùng `alembic revision` | Viết tay 45 `create_table` |
| D05 | 2026-10-28 | Bất biến bằng trigger PostgreSQL (Lock, prompt, script version) + audit append-only | Bảo vệ cả khi có người sửa DB trực tiếp | Chỉ kiểm tra ở service |
| D06 | 2026-10-28 | DEMO/PRODUCTION tách bằng cột `data_mode` + con trỏ prompt riêng mỗi chế độ | Một DB, lọc nhất quán, chuyển chế độ không mất dữ liệu; bài học DEMO không đổi prompt PRODUCTION | 2 database riêng (khó vận hành) |
| D07 | 2026-10-28 | Mock provider tạo MP4 thật bằng FFmpeg, chi phí mô phỏng có nhãn | Kiểm thử được toàn bộ pipeline + ngân sách mà không tốn tiền | Trả file tĩnh |
| D08 | 2026-10-28 | Google Flow = nhập thủ công | Flow không có API công khai; không dùng cookie/token phiên | Tự động hoá trình duyệt (vi phạm điều khoản) |
| D09 | 2026-10-28 | Chấm ý tưởng, QC kỹ thuật, KPI, ngân sách = code xác định | Minh bạch, lặp lại được, không dùng LLM cho phép tính | Để LLM chấm |
| D10 | 2026-10-28 | QC: tiêu chí AUTO không cho người chấm vượt điểm máy đo; MANUAL bắt buộc người chấm | Tiêu chí không kiểm chứng tự động phải do người đánh giá | Chấm toàn tự động |
| D11 | 2026-10-28 | Bộ lọc tuân thủ: mọi "sữa" (trừ "sữa mẹ") gắn tuổi < 24 tháng là CRITICAL | NĐ 100/2014/NĐ-CP; chuỗi bán sữa cần an toàn pháp lý tối đa, người duyệt có thể sửa nội dung | Chỉ bắt "sữa công thức" (bỏ sót) |
| D12 | 2026-10-28 | Nguyên tắc 4 mắt: người tạo Lock/RCA không tự duyệt (trừ Super Admin) | Kiểm soát nội bộ | Không ràng buộc |
| D13 | 2026-10-28 | Cookie httpOnly + CSRF double-submit; gateway Nginx cùng origin | An toàn hơn lưu token ở localStorage | Bearer trong localStorage |
| D14 | 2026-10-28 | Cấu hình API URL của web tại runtime (`/runtime-config.js`) | Không phải build lại khi đổi môi trường | NEXT_PUBLIC_* (build-time) |
| D15 | 2026-10-28 | LLM thật mặc định `claude-opus-5-5`, `output_config.format` JSON schema, `fallbacks="default"` | Theo hướng dẫn SDK chính thức; chỉ bật ở PRODUCTION khi admin nhập key | Gọi HTTP thủ công |
| D16 | 2026-10-28 | Next 15.5.28 + zod 4 + override postcss/sharp | Vá CVE (npm audit 0 lỗ hổng) | Giữ bản có lỗ hổng |
| D17 | 2026-10-28 | Ghi `agent_executions` RUNNING bằng session độc lập, khoá dự án `FOR NO KEY UPDATE` | Log lỗi không mất khi rollback; tránh khoá chéo với FK | Ghi cùng transaction (mất log khi lỗi) |
| D18 | 2026-10-28 | Gửi tác vụ Celery sau commit (event `after_commit`) | Worker không bao giờ đọc dữ liệu chưa commit | Gửi ngay trong request |
| D19 | 2026-10-29 | Chế độ AUTO (CEO chốt): tự duyệt kịch bản khi không có lỗi storyboard/vi phạm CRITICAL (gọi `approve_script` dưới tài khoản người bấm), tự lồng giọng Voice Profile M04 rồi dựng → dừng ở FINAL_QC; phê duyệt & xuất bản vẫn do người | CEO cần "nhập chủ đề là ra video"; bộ lọc D11 vẫn chặn nội dung rủi ro pháp lý | Luôn tự duyệt (rủi ro pháp lý); giữ duyệt tay (không tự động trọn vẹn) |
| D20 | 2026-10-29 | Video AI (Veo/Vertex) nhận ảnh Character Lock làm tham chiếu "asset", cấm chữ/logo trong khung hình, không tạo tiếng nói; logo/phụ đề/giọng ghép ở M06 | AI vẽ chữ tiếng Việt & logo sai, mặt nhân vật trôi giữa cảnh; giọng TTS M04 đồng nhất | Veo tự nói (giọng khác nhau mỗi cảnh) |
| D21 | 2026-10-30 | Provider thử nghiệm `flow_cdp` (CEO chốt, thay một phần D08): Playwright điều khiển Chrome riêng đã đăng nhập Flow qua CDP 127.0.0.1, mỗi lần 1 cảnh (khoá Redis), chờ video mới rồi tải về; gặp đăng nhập/CAPTCHA hoặc quá giờ → chờ thủ công, không tự gửi lại; tắt mặc định | Dùng lượt của gói Google (0đ) thay vì trả phí Vertex | CEO chấp nhận rủi ro bị hạn chế tài khoản & giao diện Flow đổi làm hỏng bộ chọn; `manual_flow` và `veo_vertex` vẫn giữ làm phương án dự phòng |
