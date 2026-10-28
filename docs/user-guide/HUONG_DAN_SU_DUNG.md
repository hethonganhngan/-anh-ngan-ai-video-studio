# Hướng dẫn sử dụng — Ánh Ngân AI Video Studio

## 1. Vai trò & việc chính

| Vai trò | Việc chính | Màn hình hay dùng |
|---|---|---|
| CEO / Super Admin | Theo dõi KPI, phê duyệt phát hành, khôi phục dữ liệu | M01, M07, M15 |
| Quản trị hệ thống | Người dùng, API, ngân sách, backup, sức khoẻ hệ thống | M15, M14 |
| Quản lý sản xuất (PM) | Duyệt kịch bản, khoá nhân vật, điều phối, phê duyệt, CAPA, bài học | M03, M04, M05, M07, M08, M09, M11 |
| Người sáng tạo nội dung | Tạo brief, chạy AI viết kịch bản, sửa storyboard | M02, M03 |
| Biên tập video | Tạo/nhập cảnh, dựng timeline, render | M05, M06, M12 |
| Kiểm định chất lượng | QC cảnh & tổng thể, lập RCA, kiểm chứng CAPA | M07, M08 |
| Người phát hành | Lịch đăng, xuất gói, ghi URL, nhập số liệu | M10 |
| Người xem | Xem báo cáo | M01, M11 |

Thanh trên cùng luôn hiện **DEMO — dữ liệu mẫu** hoặc **PRODUCTION**. Ở DEMO: video do Mock Provider tạo (không phải AI thật), chi phí là mô phỏng, không thể tự xuất bản.

## 2. Quy trình chuẩn một video (SOP)

1. **M02 — Tạo video**: chọn kênh, nhập chủ đề, mục tiêu, khách hàng, thời lượng (mỗi cảnh 8 giây), nhân vật/bối cảnh/giọng, CTA, ngân sách, mức tự động hoá. Xem chi phí ước tính → *Tạo*. Bấm 2 lần không tạo trùng.
2. **M03 — Kịch bản**: *Tạo 3 ý tưởng* → xem điểm (hook, thương hiệu, khách hàng, khả thi, tuân thủ) → chọn → *Viết kịch bản*. Sửa hook/lời thoại (mỗi cảnh 1 hành động, tối đa 2 câu thoại) → *Lưu phiên bản*. PM *Duyệt kịch bản* → hệ thống tạo prompt 9 phần cho từng cảnh.
   - Bộ lọc tuân thủ chặn: quảng cáo sữa cho trẻ dưới 24 tháng, tuyên bố chữa bệnh, từ tuyệt đối hoá ("tốt nhất", "100%"…).
3. **M04 — Nhân vật** (làm 1 lần/nhân vật): tạo hồ sơ, tải ảnh chính diện / 3/4 / toàn thân, xác nhận consent → *Tạo Character Lock* → người khác (PM/CEO) *Duyệt*. Bản đã duyệt không sửa được; muốn đổi phải tạo phiên bản mới.
4. **M05 — Sản xuất**: *Kiểm tra tài nguyên* (Lock, consent, ngân sách) → *Tạo cảnh*. Cảnh lỗi được thử lại tự động tối đa 3 lần; quá giới hạn → sửa prompt rồi *Tạo lại*. Dùng Google Flow: tạo clip trên Flow, tải về, bấm *Nhập từ Flow* đúng cảnh (9:16, ≥ 720×1280).
5. **M06 — Editor**: sắp xếp/cắt cảnh, thêm voice-over, nhạc nền, logo, phụ đề, thumbnail → *Lưu* → *Export MP4*.
6. **M07 — QC**: xem video + gợi ý A07 (âm lượng LUFS, khung đen…). Chấm đủ 10 tiêu chí; tiêu chí *AUTO* không chấm cao hơn máy đo. Đạt khi **≥ 98/100**, không còn lỗi CRITICAL/MAJOR mở. Người có quyền bấm *Phê duyệt* (hoặc *Từ chối* kèm lý do).
7. **M10 — Phát hành**: tạo bài đăng (nền tảng, caption, hashtag, ngày đăng) → *Xuất file* (ZIP gồm MP4, thumbnail, phụ đề, caption) → đăng thủ công → *Đánh dấu đã đăng* + URL. Nhập số liệu (lượt xem, thích, bình luận, chia sẻ, giữ chân, chuyển đổi) hoặc import CSV.
8. **M01 — Dashboard**: theo dõi KPI; bấm biểu tượng ⓘ để xem công thức & nguồn dữ liệu.

## 3. Khi có lỗi — Feedback Loop 360° (M08)

| Bước | Làm gì | Bắt buộc |
|---|---|---|
| INTAKE | Tạo hồ sơ (hoặc từ lỗi QC) | Tiêu đề, nguồn |
| VALIDATE | Xác thực, phân loại FACT/HYPOTHESIS/UNKNOWN | ≥ 1 bằng chứng |
| TRIAGE | Ưu tiên P0–P3, người phụ trách, deadline, KPI trước/mục tiêu | Owner |
| ROOT CAUSE | 5 Whys (có thể dùng gợi ý A08 — chỉ là giả thuyết) | ≥ 3 câu trả lời, mức chắc chắn |
| CAPA | Hành động khắc phục/phòng ngừa; **người khác** duyệt | ≥ 1 CORRECTIVE |
| ASSIGN | Giao việc, hoàn thành từng CAPA | Bằng chứng hoàn thành |
| VERIFY | Đo lại KPI; không đạt → REOPENED | Bằng chứng, KPI sau đạt mục tiêu |
| STANDARDIZE | Cập nhật SOP/prompt/checklist, tạo bài học | Ghi chú chuẩn hoá |
| CLOSED | Đóng hồ sơ | Kiểm chứng đạt |

## 4. Bài học (M09)

Bài học từ hồ sơ đã kiểm chứng → *Gửi duyệt* → PM/CEO *Duyệt* → *Áp dụng* (tạo phiên bản prompt chuẩn mới, mọi video sau dùng ngay) → nếu phát sinh vấn đề: *Rollback* (cần lý do). Tìm theo kênh, nhân vật, loại lỗi, nhà cung cấp.

## 5. Quản trị (M15)

- **Người dùng/Vai trò**: tạo tài khoản theo vai trò; không tự khoá chính mình; chỉ Super Admin tạo Super Admin.
- **API Connections**: nhập API key (chỉ hiện 4 ký tự cuối), *Test* để xác minh. Chỉ trạng thái **VERIFIED** mới là kết nối thật.
- **Ngân sách**: hạn mức ngày/tháng theo toàn hệ thống, kênh, nhà cung cấp; ngưỡng cảnh báo; *hard stop* chặn phát sinh chi phí.
- **Demo/Production**: gõ đúng tên chế độ để chuyển. Dữ liệu hai chế độ tách biệt.
- **Backup**: tạo bản sao lưu; khôi phục cần gõ `RESTORE <tên file>` (chỉ Super Admin).
- **Audit Log**: mọi thao tác quan trọng được ghi lại, không thể sửa/xoá.

## 6. Câu hỏi thường gặp

- *Vì sao không tạo cảnh được?* → Xem báo cáo *Kiểm tra tài nguyên*: thiếu Character Lock, chưa consent, hoặc vượt ngân sách.
- *Vì sao không phê duyệt được?* → Cần quyền `project.approve`, QC người chấm ≥ 98 trên bản render mới nhất, không còn lỗi nghiêm trọng mở.
- *Video DEMO có đăng được không?* → Chỉ xuất file để xem thử; không được tự động xuất bản.
