"""10 tiêu chí QC. method: AUTO (đo tự động — người chấm không được vượt điểm máy đo),
ASSISTED (máy gợi ý, người xác nhận), MANUAL (chỉ người đánh giá được)."""

CRITERIA = [
    {"key": "hook", "label": "Hook", "method": "ASSISTED", "desc": "Hook rõ trong 3 giây đầu, gây chú ý"},
    {"key": "script", "label": "Kịch bản", "method": "ASSISTED", "desc": "Mạch lạc, đúng storyboard, ≤ 2 thoại/cảnh"},
    {"key": "character", "label": "Nhân vật", "method": "MANUAL", "desc": "Nhất quán khuôn mặt/trang phục theo Character Lock"},
    {"key": "setting", "label": "Bối cảnh", "method": "MANUAL", "desc": "Nhất quán theo Scene Lock, phù hợp thương hiệu"},
    {"key": "visual", "label": "Hình ảnh", "method": "AUTO", "desc": "1080x1920, 30fps, không khung đen, không méo"},
    {"key": "voice", "label": "Giọng nói", "method": "MANUAL", "desc": "Đúng Voice Lock, accent, rõ ràng"},
    {"key": "lipsync", "label": "Khẩu hình", "method": "MANUAL", "desc": "Khẩu hình khớp lời thoại"},
    {"key": "audio", "label": "Âm thanh", "method": "AUTO", "desc": "Có âm thanh, độ ồn -20..-12 LUFS, không lặng dài"},
    {"key": "brand", "label": "Thương hiệu", "method": "ASSISTED", "desc": "Logo, CTA, giọng thương hiệu đúng Brand DNA"},
    {"key": "compliance", "label": "Tuân thủ & chính xác", "method": "ASSISTED",
     "desc": "Không vi phạm quy định quảng cáo, không thông tin chưa kiểm chứng"},
]
KEYS = [c["key"] for c in CRITERIA]
BY_KEY = {c["key"]: c for c in CRITERIA}
