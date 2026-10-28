# Ma trận chức năng — 15 màn hình × backend × kiểm thử

| Mã | Màn hình | Route | Module | Chức năng chính | Test backend | E2E |
|---|---|---|---|---|---|---|
| M01 | Dashboard CEO | `/dashboard` | B11 | 14 KPI có công thức + nguồn, lọc kênh/kỳ/dự án/người phụ trách, biểu đồ, top video, cảnh báo ngân sách | test_end_to_end, test_publishing_analytics | m01 |
| M02 | Trung tâm tạo video | `/create` | B01 | Form đầy đủ, lô video, ước tính chi phí, idempotency key | test_generation (idempotency, batch, validation) | m02 |
| M03 | AI Script & Storyboard | `/scripts` | B02, B04 | 3 ý tưởng + chấm, hook, kịch bản, cảnh 8s, sửa → version, duyệt, prompt 9 phần | test_end_to_end, test_feedback_lessons | m03 |
| M04 | Character & Voice | `/characters` | B03 | Character ID, ảnh 3 góc, Character/Voice/Scene Lock bất biến, consent, lịch sử | test_characters | m04 |
| M05 | Video Production | `/production` | B05 | Mock/Flow/Real API, job, retry giới hạn, nhập Flow, chi phí, ngân sách | test_generation | m05 |
| M06 | AI Video Editor | `/editor` | B06 | Timeline: thứ tự, cắt, voice-over, nhạc, phụ đề, logo, thumbnail, export MP4, lịch sử | test_render_quality | m06 |
| M07 | Quality Control | `/quality` | B07 | 10 tiêu chí × 10 điểm, AUTO/ASSISTED/MANUAL, ≥98, lỗi CRITICAL, phê duyệt | test_render_quality | m07 |
| M08 | Feedback Loop 360° | `/feedback` | B08 | 8 bước, 9 trạng thái + REOPENED, 5 Whys, CAPA, bằng chứng, KPI trước/sau | test_feedback_lessons | m08 |
| M09 | AI Lessons Learned | `/lessons` | B09 | Tìm kiếm đa tiêu chí, duyệt, áp dụng vào prompt chuẩn, rollback | test_feedback_lessons | m09 |
| M10 | Publishing & Analytics | `/publishing` | B10, B11 | Lịch, caption/hashtag kiểm tra tuân thủ, xuất file, URL, analytics, CSV, so sánh | test_end_to_end, test_publishing_analytics | m10 |
| M11 | Quản lý dự án & hàng đợi | `/projects` | B01 | Danh sách, Kanban, hàng đợi, retry, cancel, job detail, lô, nhật ký | test_generation, test_render_quality | m11 |
| M12 | Thư viện tài nguyên | `/library` | media | Upload an toàn, loại, quyền sử dụng, tag, version, search, Object Storage | test_end_to_end, test_characters | m12 |
| M13 | Kênh & Brand DNA | `/channels` | B01 | 4 kênh, Brand DNA Ánh Ngân, version history | test_end_to_end | m13 |
| M14 | AI Agent Control Center | `/agents` | agents | 10 agent, model/provider, token, chi phí, latency, log, bật/tắt, giới hạn | test_admin_agents | m14 |
| M15 | Cài đặt & quản trị | `/settings` | B12 | Người dùng, vai trò, API connections (masked), ngân sách, thông báo, audit, backup, health, Demo/Production | test_admin_agents, test_auth_rbac | m15, m00 |
