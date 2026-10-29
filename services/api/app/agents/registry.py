"""Định nghĩa 10 AI Agent. Agent chỉ được thực hiện các action trong allowed_actions.
Không Agent nào có quyền phê duyệt, xuất bản hay sửa cấu hình chuẩn — các việc đó cần con người."""

RULE_ENGINE = ("internal", "rule-engine-v1")
MOCK_LLM = ("mock-llm", "mock-deterministic-v1")
DEFAULT_LLM = ("gemini", "gemini-3.8-flash")  # DEMO vẫn luôn chạy Mock (resolve_llm)

AGENTS: dict[str, dict] = {
    "A01": {"name": "AI Director", "uses_llm": False,
            "role": "Điều phối workflow end-to-end, quyết định bước kế tiếp theo mức tự động hoá, xử lý retry.",
            "allowed_actions": ["workflow.advance", "workflow.retry", "project.orchestrate"]},
    "A02": {"name": "AI Script", "uses_llm": True, "prompt_template_code": "A02.script",
            "role": "Tạo 3 ý tưởng, hook 3 giây, kịch bản, chia cảnh 8 giây và lời thoại theo Brand DNA.",
            "allowed_actions": ["script.ideas", "script.write", "script.storyboard"]},
    "A03": {"name": "AI Prompt", "uses_llm": False, "prompt_template_code": "A03.scene_prompt",
            "role": "Lắp prompt 9 phần cho từng cảnh từ Character/Scene/Voice Lock và bài học đã áp dụng.",
            "allowed_actions": ["prompt.build"]},
    "A04": {"name": "AI Character", "uses_llm": False,
            "role": "Kiểm tra Character Lock, Voice Lock, quyền sử dụng và tài nguyên trước khi tạo cảnh.",
            "allowed_actions": ["assets.validate", "character.check"]},
    "A05": {"name": "AI Video", "uses_llm": False,
            "role": "Gửi tác vụ tạo cảnh tới Video Provider, theo dõi trạng thái, lưu kết quả.",
            "allowed_actions": ["generation.submit", "generation.poll"]},
    "A06": {"name": "AI Editor", "uses_llm": False,
            "role": "Lập timeline, sinh phụ đề, dựng video FFmpeg, thumbnail.",
            "allowed_actions": ["render.plan", "render.execute", "subtitle.generate"]},
    "A07": {"name": "AI QC", "uses_llm": False,
            "role": "Kiểm tra kỹ thuật tự động (FFprobe, âm thanh, khung đen), tuân thủ nội dung; gợi ý điểm. Không phê duyệt.",
            "allowed_actions": ["qc.scene_check", "qc.final_check"]},
    "A08": {"name": "AI Feedback", "uses_llm": True, "prompt_template_code": "A08.rca",
            "role": "Tạo Feedback Case từ lỗi QC/analytics, gợi ý ưu tiên và 5 Whys (dạng HYPOTHESIS).",
            "allowed_actions": ["feedback.create_from_qc", "feedback.triage_suggest", "feedback.rca_suggest"]},
    "A09": {"name": "AI Learning", "uses_llm": True, "prompt_template_code": "A09.lesson",
            "role": "Soạn bài học từ hồ sơ đã xác minh, tìm bài học liên quan cho Prompt Engine. Không tự áp dụng.",
            "allowed_actions": ["lesson.draft", "lesson.search"]},
    "A10": {"name": "AI Analytics", "uses_llm": False,
            "role": "Tính KPI, so sánh hiệu quả video, phát hiện bất thường (phép tính xác định, không dùng LLM).",
            "allowed_actions": ["analytics.compute", "analytics.insights"]},
}
