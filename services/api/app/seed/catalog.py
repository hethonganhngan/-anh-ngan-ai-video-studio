"""Dữ liệu cấu hình chuẩn: 4 kênh + Brand DNA, prompt template, provider."""

ANNGAN_FORBIDDEN = [
    "tốt nhất", "số 1", "số một", "hàng đầu", "chữa bệnh", "chữa khỏi", "điều trị", "đặc trị", "thần kỳ", "thần dược",
    "thay thế sữa mẹ", "tốt hơn sữa mẹ", "như sữa mẹ", "100% an toàn", "cam kết tăng cân", "tăng chiều cao vượt trội",
    "phòng ngừa mọi bệnh", "không có tác dụng phụ",
]

BRAND_VOICE = ["Gần gũi", "Rõ ràng", "Ân cần", "Trung thực", "Có trách nhiệm"]

CHANNELS = [
    {
        "code": "ANNGAN", "name": "Hệ thống Sữa Ánh Ngân", "platforms": ["FACEBOOK", "TIKTOK", "ZALO", "YOUTUBE"],
        "description": "Kênh thương hiệu chính của chuỗi cửa hàng Mẹ & Bé Ánh Ngân.",
        "brand": {
            "slogan": "TRAO NIỀM TIN – NHẬN GIÁ TRỊ",
            "brand_promise": "AN TÂM CHO MỖI LỰA CHỌN",
            "big_idea": "MỖI LỰA CHỌN, MỘT NIỀM AN TÂM",
            "brand_voice": BRAND_VOICE,
            "audience": "Mẹ bỉm sữa 22–38 tuổi, gia đình có con 0–6 tuổi tại địa phương; quan tâm chất lượng, nguồn gốc, tư vấn tận tâm.",
            "content_pillars": ["Tư vấn chọn sản phẩm theo nhu cầu", "Câu chuyện khách hàng thật", "Kiến thức chăm con có nguồn",
                                "Hậu trường cửa hàng & quy trình kiểm hàng", "Ưu đãi minh bạch"],
            "cta_rules": ["CTA mời đến cửa hàng hoặc nhắn tin để được tư vấn, không hối thúc mua",
                          "Không hứa công dụng; chỉ nêu thông tin đã kiểm chứng trên nhãn/nhà sản xuất",
                          "Không quảng cáo sữa thay thế sữa mẹ cho trẻ dưới 24 tháng (Nghị định 100/2014/NĐ-CP)"],
            "quality_rules": ["Video dọc 9:16, 1080x1920", "Mỗi cảnh 8 giây, 1 hành động chính, ≤ 2 câu thoại",
                              "Hook trong 3 giây đầu", "Logo Ánh Ngân xuất hiện ≥ 1 lần", "Phụ đề tiếng Việt đầy đủ dấu",
                              "QC ≥ 98/100, không Critical Error"],
            "publishing_rules": ["Chỉ đăng video đã được phê duyệt", "Kiểm tra caption bằng bộ lọc tuân thủ trước khi đăng",
                                 "Ghi URL bài đăng vào hệ thống trong 24h"],
            "forbidden_terms": ANNGAN_FORBIDDEN,
        },
    },
    {
        "code": "CNM", "name": "Chuyện Nhà Mình", "platforms": ["FACEBOOK", "TIKTOK"],
        "description": "Series đời thường gia đình trẻ, ấm áp, gần gũi.",
        "brand": {
            "slogan": "Chuyện nhỏ nhà mình, tình thương lớn", "brand_promise": "Kể chuyện thật, gần gũi, tử tế",
            "big_idea": "Mỗi gia đình là một câu chuyện đáng trân trọng", "brand_voice": ["Ấm áp", "Hài hước nhẹ", "Chân thật"],
            "audience": "Vợ chồng trẻ 25–40 tuổi, có con nhỏ.",
            "content_pillars": ["Khoảnh khắc gia đình", "Bài học nuôi dạy con", "Sẻ chia việc nhà"],
            "cta_rules": ["CTA mời theo dõi kênh/chia sẻ câu chuyện", "Không bán hàng trực tiếp"],
            "quality_rules": ["9:16", "Nhân vật nhất quán theo Character Lock", "Không nội dung gây tranh cãi"],
            "publishing_rules": ["Đăng 18:00–21:00"], "forbidden_terms": ANNGAN_FORBIDDEN,
        },
    },
    {
        "code": "BPCD", "name": "Ba Phi Chuyện Đời", "platforms": ["TIKTOK", "YOUTUBE"],
        "description": "Nhân vật Ba Phi kể chuyện đời, giọng miền Tây dí dỏm, rút ra bài học sống.",
        "brand": {
            "slogan": "Chuyện đời kể bằng cái tình", "brand_promise": "Vui mà thấm, kể mà thật",
            "big_idea": "Đời có lý của đời", "brand_voice": ["Dí dỏm", "Mộc mạc", "Sâu sắc"],
            "audience": "Người lớn 25–55 tuổi yêu thích chuyện đời, văn hoá miền Nam.",
            "content_pillars": ["Chuyện đời thường", "Bài học sống", "Văn hoá miền quê"],
            "cta_rules": ["CTA mời bình luận chia sẻ trải nghiệm"],
            "quality_rules": ["Giữ Voice Lock giọng Ba Phi", "Không phát ngôn chính trị, tôn giáo"],
            "publishing_rules": ["Đăng tối"], "forbidden_terms": ANNGAN_FORBIDDEN,
        },
    },
    {
        "code": "KTMB", "name": "Kiến thức Mẹ & Bé", "platforms": ["FACEBOOK", "TIKTOK", "YOUTUBE"],
        "description": "Kiến thức chăm sóc mẹ và bé có dẫn nguồn, dễ hiểu, an toàn.",
        "brand": {
            "slogan": "Hiểu đúng – Chăm đúng", "brand_promise": "Kiến thức có nguồn, dễ áp dụng",
            "big_idea": "Mẹ hiểu con, con lớn khoẻ", "brand_voice": ["Rõ ràng", "Ân cần", "Có căn cứ"],
            "audience": "Mẹ mang thai và mẹ có con 0–6 tuổi.",
            "content_pillars": ["Dinh dưỡng theo độ tuổi (khuyến nghị chính thống)", "Chăm sóc hằng ngày", "Dấu hiệu cần gặp bác sĩ"],
            "cta_rules": ["Luôn khuyến nghị tham khảo ý kiến bác sĩ/chuyên gia dinh dưỡng", "Ưu tiên khuyến khích nuôi con bằng sữa mẹ"],
            "quality_rules": ["Mọi thông tin y khoa phải có nguồn kiểm chứng", "Không chẩn đoán, không kê đơn"],
            "publishing_rules": ["Kiểm duyệt chuyên môn trước khi đăng"], "forbidden_terms": ANNGAN_FORBIDDEN,
        },
    },
]

BASE_NEGATIVE = ("chữ méo hoặc sai chính tả, logo sai, watermark, biến dạng tay/ngón tay, khuôn mặt thay đổi giữa các cảnh, "
                 "trang phục thay đổi so với Character Lock, mờ nhoè, nhấp nháy, nội dung bạo lực, sản phẩm thương hiệu "
                 "đối thủ, bao bì sữa công thức cho trẻ dưới 24 tháng, trẻ em trong tình huống nguy hiểm")

PROMPT_TEMPLATES = [
    {
        "code": "A02.script", "name": "Kịch bản video dọc", "agent_code": "A02",
        "purpose": "System prompt cho AI Script: ý tưởng, hook, kịch bản, chia cảnh.",
        "content": (
            "Bạn là biên kịch video ngắn cho kênh {{ channel_name }} thuộc Hệ thống Sữa Ánh Ngân.\n"
            "Brand DNA: slogan '{{ slogan }}', lời hứa '{{ brand_promise }}', Big Idea '{{ big_idea }}'.\n"
            "Giọng thương hiệu: {{ brand_voice }}.\n"
            "QUY TẮC BẮT BUỘC:\n"
            "- Video dọc 9:16, mỗi cảnh {{ scene_seconds }} giây, đúng 1 hành động chính, tối đa 2 câu thoại/cảnh.\n"
            "- Hook gây chú ý trong 3 giây đầu.\n"
            "- KHÔNG tự tạo công dụng sản phẩm, số liệu, chứng nhận hay thông tin y khoa chưa kiểm chứng.\n"
            "- KHÔNG quảng cáo sữa thay thế sữa mẹ cho trẻ dưới 24 tháng.\n"
            "- Tránh các từ: {{ forbidden_terms }}.\n"
            "- Tiếng Việt có dấu đầy đủ, tự nhiên, gần gũi.\n"
            "{% for r in rules %}- {{ r }}\n{% endfor %}"
        ),
        "negative_prompt": "",
    },
    {
        "code": "A03.scene_prompt", "name": "Prompt cảnh 9 phần", "agent_code": "A03",
        "purpose": "Template lắp prompt tạo video cho từng cảnh.",
        "content": (
            "[1. LOẠI CẢNH] {{ scene_type }}\n"
            "[2. NHÂN VẬT] {{ characters }}\n"
            "[3. HÀNH ĐỘNG] {{ action }}\n"
            "[4. BỐI CẢNH] {{ setting }}\n"
            "[5. MÁY QUAY] {{ camera }}\n"
            "[6. ÁNH SÁNG] {{ lighting }}\n"
            "[7. ÂM THANH] {{ sound }}\n"
            "[8. THOẠI] {{ dialogue }}\n"
            "[9. NEGATIVE PROMPT] {{ negative }}\n"
            "Định dạng: video dọc {{ aspect_ratio }}, {{ duration }} giây, 1080x1920, chuyển động tự nhiên."
            "{% for r in rules %}\nLưu ý: {{ r }}{% endfor %}"
        ),
        "negative_prompt": BASE_NEGATIVE,
    },
    {
        "code": "A08.rca", "name": "Phân tích nguyên nhân gốc (5 Whys)", "agent_code": "A08",
        "purpose": "Gợi ý 5 Whys và CAPA — luôn đánh dấu HYPOTHESIS cho đến khi có bằng chứng.",
        "content": ("Phân tích lỗi sản xuất video sau bằng 5 Whys. Chỉ kết luận FACT khi có bằng chứng. "
                    "Lỗi: {{ title }}. Mô tả: {{ description }}. Bằng chứng: {{ evidence }}."),
        "negative_prompt": "",
    },
    {
        "code": "A09.lesson", "name": "Soạn bài học", "agent_code": "A09",
        "purpose": "Tóm tắt bài học từ hồ sơ Feedback đã xác minh.",
        "content": ("Soạn bài học ngắn gọn, có thể áp dụng, từ hồ sơ {{ code }}: nguyên nhân {{ root_cause }}, "
                    "CAPA {{ capa }}, kết quả xác minh {{ verification }}."),
        "negative_prompt": "",
    },
]

VEO_VERTEX_CONFIG = {
    "adapter": "veo_vertex", "model": "veo-3.1-fast-generate-001", "location": "us-central1", "resolution": "720p",
    "generate_audio": False, "speech_in_video": False, "max_duration_sec": 8, "supported_aspects": ["9:16", "16:9"],
    "note": "Dùng được tín dụng dùng thử Google Cloud. Bật Vertex AI API, tạo service account (Vertex AI User) và "
            "nạp file khoá JSON tại 'Sửa'. Gửi kèm ảnh Character Lock (M04); thoại do giọng M04 (TTS) lồng ở bước dựng, "
            "logo/phụ đề ghép ở M06. Giá Veo 3.1 Fast ~0,10–0,15 USD/giây (tham khảo, kiểm tra bảng giá Google).",
}

PROVIDERS = [
    {"provider_type": "VIDEO", "provider_code": "mock", "name": "Mock Video Provider (DEMO)", "is_enabled": True,
     "connection_status": "BUILTIN", "unit_cost": 1500, "cost_unit": "SECOND",
     "config": {"note": "Tạo MP4 thật bằng FFmpeg; không phải AI. Chỉ DEMO."}},
    {"provider_type": "VIDEO", "provider_code": "manual_flow", "name": "Google Flow (nhập thủ công)", "is_enabled": True,
     "connection_status": "BUILTIN", "unit_cost": 0, "cost_unit": "SECOND",
     "config": {"note": "Flow không có API công khai. Tạo cảnh trên Flow rồi tải lên tại M05."}},
    {"provider_type": "VIDEO", "provider_code": "veo_vertex", "name": "Google Veo (Vertex AI) — API chính thức",
     "is_enabled": False, "connection_status": "NOT_CONFIGURED", "unit_cost": 3900, "cost_unit": "SECOND",
     "config": VEO_VERTEX_CONFIG},
    {"provider_type": "VIDEO", "provider_code": "gemini_omni", "name": "Google Gemini Omni Flash — tạo video AI",
     "is_enabled": False, "connection_status": "NOT_CONFIGURED", "unit_cost": 2600, "cost_unit": "SECOND",
     "config": {"adapter": "gemini_omni", "model": "gemini-omni-1.1-flash", "resolution": "720p", "background": True,
                "speech_in_video": False, "max_duration_sec": 10, "supported_aspects": ["9:16", "16:9"],
                "note": "Key lấy tại aistudio.google.com (bật thanh toán). Giá ~0,10 USD/giây 720p. "
                        "Thoại tiếng Việt dùng Gemini TTS, video chỉ có âm thanh môi trường."}},
    {"provider_type": "TTS", "provider_code": "gemini_tts", "name": "Google Gemini TTS — giọng đọc tiếng Việt",
     "is_enabled": False, "connection_status": "NOT_CONFIGURED", "unit_cost": 12, "cost_unit": "SECOND",
     "config": {"adapter": "gemini_tts", "model": "gemini-3.8-flash-tts", "default_voice": "Kore", "style_prompt": True,
                "note": "Dùng chung key Gemini. ~25 token/giây âm thanh; giá ~12 VND/giây (theo bảng giá 2027)."}},
    {"provider_type": "LLM", "provider_code": "gemini_llm", "name": "Google Gemini — kịch bản & phân tích (A02/A08/A09)",
     "is_enabled": False, "connection_status": "NOT_CONFIGURED", "unit_cost": 0, "cost_unit": "TOKEN",
     "config": {"adapter": "gemini_llm", "model": "gemini-3.8-flash", "thinking_level": "medium",
                "note": "Dùng chung key Gemini. Chọn model cho từng agent tại M14 (provider 'gemini')."}},
    {"provider_type": "LLM", "provider_code": "anthropic", "name": "Anthropic Claude", "is_enabled": False,
     "connection_status": "NOT_CONFIGURED", "unit_cost": 0, "cost_unit": "TOKEN",
     "config": {"model": "claude-opus-5-5"}},
    {"provider_type": "TTS", "provider_code": "tts_none", "name": "Text-to-Speech (chưa kết nối)", "is_enabled": False,
     "connection_status": "NOT_CONFIGURED", "unit_cost": 0, "cost_unit": "CHAR",
     "config": {"note": "Voice-over hiện tải lên thủ công (file thu âm có consent)."}},
    {"provider_type": "PUBLISH", "provider_code": "facebook_pages", "name": "Facebook Pages (Graph API)", "is_enabled": False,
     "connection_status": "NOT_CONFIGURED", "unit_cost": 0, "cost_unit": "POST", "config": {}},
    {"provider_type": "PUBLISH", "provider_code": "tiktok_content", "name": "TikTok Content Posting API", "is_enabled": False,
     "connection_status": "NOT_CONFIGURED", "unit_cost": 0, "cost_unit": "POST", "config": {}},
    {"provider_type": "PUBLISH", "provider_code": "youtube_data", "name": "YouTube Data API v3", "is_enabled": False,
     "connection_status": "NOT_CONFIGURED", "unit_cost": 0, "cost_unit": "POST", "config": {}},
    {"provider_type": "PUBLISH", "provider_code": "zalo_oa", "name": "Zalo Official Account API", "is_enabled": False,
     "connection_status": "NOT_CONFIGURED", "unit_cost": 0, "cost_unit": "POST", "config": {}},
    {"provider_type": "STORAGE", "provider_code": "object_storage", "name": "Object Storage (Local/S3/MinIO)",
     "is_enabled": True, "connection_status": "BUILTIN", "unit_cost": 0, "cost_unit": "GB", "config": {}},
]

DEMO_USERS = [
    ("pm@anhngan.local", "Nguyễn Thị Quản Lý (DEMO)", "PRODUCTION_MANAGER"),
    ("sysadmin@anhngan.local", "Trần Quản Trị (DEMO)", "SYSTEM_ADMIN"),
    ("creator@anhngan.local", "Lê Sáng Tạo (DEMO)", "CONTENT_CREATOR"),
    ("editor@anhngan.local", "Phạm Biên Tập (DEMO)", "VIDEO_EDITOR"),
    ("qc@anhngan.local", "Võ Kiểm Định (DEMO)", "QUALITY_REVIEWER"),
    ("publisher@anhngan.local", "Đỗ Phát Hành (DEMO)", "PUBLISHER"),
    ("viewer@anhngan.local", "Hoàng Người Xem (DEMO)", "VIEWER"),
]
