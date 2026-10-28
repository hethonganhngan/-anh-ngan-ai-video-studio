"""A02 AI Script — ý tưởng, hook, kịch bản, storyboard.

- Mock (DEMO): nội dung xác định từ brief + Brand DNA, KHÔNG tự tạo công dụng sản phẩm.
- Thật (PRODUCTION): Claude trả JSON theo schema; kết quả vẫn qua cùng bộ kiểm tra cảnh & tuân thủ.
- Chấm ý tưởng: rubric xác định (không dùng LLM) để minh bạch & lặp lại được.
"""
import hashlib
import math

from jinja2.sandbox import SandboxedEnvironment

from app.modules.quality.compliance import has_critical, scan

_env = SandboxedEnvironment(autoescape=False)

IDEA_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["ideas"],
    "properties": {"ideas": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["title", "angle", "hook", "summary"],
        "properties": {"title": {"type": "string"}, "angle": {"type": "string"}, "hook": {"type": "string"},
                       "summary": {"type": "string"}}}}},
}
SCRIPT_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["title", "hook", "body", "cta", "scenes"],
    "properties": {
        "title": {"type": "string"}, "hook": {"type": "string"}, "body": {"type": "string"}, "cta": {"type": "string"},
        "scenes": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["title", "scene_type", "action", "dialogue", "setting", "camera", "lighting", "sound"],
            "properties": {
                "title": {"type": "string"}, "scene_type": {"type": "string"}, "action": {"type": "string"},
                "dialogue": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                                        "required": ["speaker", "text"],
                                                        "properties": {"speaker": {"type": "string"}, "text": {"type": "string"}}}},
                "setting": {"type": "string"}, "camera": {"type": "string"}, "lighting": {"type": "string"},
                "sound": {"type": "string"}}}},
    },
}

ANGLES = [
    ("STORY", "Câu chuyện khách hàng", "Kể một tình huống thật của mẹ và cách Ánh Ngân đồng hành"),
    ("QA", "Hỏi – đáp tư vấn", "Tư vấn viên trả lời câu hỏi thường gặp, rõ ràng và trung thực"),
    ("BEHIND", "Hậu trường & quy trình", "Cho thấy quy trình kiểm hàng, bảo quản, tư vấn tại cửa hàng"),
]


def render_system_prompt(template: str, ctx_vars: dict) -> str:
    return _env.from_string(template).render(**ctx_vars)


def _h(*parts) -> int:
    return int(hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest(), 16)


def mock_ideas(brief: dict) -> dict:
    topic = brief["topic"].rstrip(".")
    aud = brief.get("target_audience") or "các mẹ"
    hooks = {
        "STORY": f"Mẹ ơi, {topic.lower()} — chuyện này nhà nào cũng từng gặp?",
        "QA": f"3 điều mẹ cần hỏi trước khi quyết định: {topic.lower()}",
        "BEHIND": f"Ở Ánh Ngân, trước khi tư vấn về {topic.lower()}, tụi mình làm gì?",
    }
    ideas = []
    for code, name, desc in ANGLES:
        ideas.append({"title": f"{name}: {topic}", "angle": code, "hook": hooks[code],
                      "summary": f"{desc}. Đối tượng: {aud}. Thông điệp: {brief.get('big_idea', '')}."})
    return {"ideas": ideas}


def score_idea(idea: dict, brief: dict) -> dict:
    """Rubric 5 tiêu chí x 10 điểm → quy về thang 100. Giải thích từng điểm."""
    hook = idea.get("hook", "")
    words = len(hook.split())
    text = " ".join([idea.get("title", ""), hook, idea.get("summary", "")]).lower()
    s_hook = 4 + (3 if "?" in hook or any(ch.isdigit() for ch in hook) else 0) + (3 if 5 <= words <= 16 else (1 if words <= 22 else 0))
    pillars = [p.lower() for p in brief.get("content_pillars", [])]
    pillar_hit = any(any(w in text for w in p.split()[:2]) for p in pillars) if pillars else False
    s_brand = 6 + (2 if pillar_hit else 0) + (2 if any(k in text for k in ("ánh ngân", "tư vấn", "an tâm", "niềm tin")) else 0)
    s_aud = 6 + (2 if any(k in text for k in ("mẹ", "bé", "con", "gia đình", "ba")) else 0) + (2 if brief.get("target_audience") else 0)
    s_feas = 9 if idea.get("angle") in ("QA", "BEHIND") else 8
    findings = scan(text, brief.get("forbidden_terms"))
    s_comp = 0 if has_critical(findings) else max(0, 10 - 3 * len(findings))
    scores = {"hook": min(10, s_hook), "brand_fit": min(10, s_brand), "audience_fit": min(10, s_aud),
              "feasibility": s_feas, "compliance": s_comp}
    total = round(sum(scores.values()) * 2)
    return {"scores": scores, "total": total, "compliance_findings": [f.to_dict() for f in findings],
            "method": "Rubric xác định: hook(≤16 từ, câu hỏi/con số), brand_fit(trụ cột nội dung), audience_fit, feasibility, compliance(bộ lọc tuân thủ)"}


def mock_script(brief: dict, idea: dict, characters: list[dict], scene_seconds: int) -> dict:
    n = max(1, math.ceil(brief["duration_sec"] / scene_seconds))
    topic = brief["topic"].rstrip(".")
    cta = brief.get("cta") or "Mẹ ghé cửa hàng Ánh Ngân gần nhất hoặc nhắn tin để được tư vấn theo nhu cầu của bé nhé."
    mom = next((c for c in characters if "mẹ" in c["name"].lower()), None) or {"name": "Mẹ Lan", "code": ""}
    staff = next((c for c in characters if c is not mom), None) or {"name": "Chị Ngân – tư vấn viên", "code": ""}
    setting = brief.get("setting") or "Cửa hàng Ánh Ngân sáng sủa, kệ sản phẩm gọn gàng, quầy tư vấn"
    beats = [
        ("HOOK", f"{mom['name']} cầm hai hộp sản phẩm, nhìn băn khoăn về camera", [(mom["name"], idea["hook"])],
         "Cận mặt, máy quay đặt ngang tầm mắt, đẩy nhẹ vào", "Ánh sáng tự nhiên ban ngày, ấm"),
        ("LẮNG NGHE", f"{staff['name']} mỉm cười tiến lại, cúi người lắng nghe", [(staff["name"], "Chị đừng lo, mình cùng xem nhu cầu của bé trước nhé.")],
         "Trung cảnh hai người, máy quay cố định", "Ánh sáng cửa hàng dịu"),
        ("TƯ VẤN", f"{staff['name']} chỉ vào thông tin trên nhãn sản phẩm", [(staff["name"], "Mình luôn đọc kỹ thông tin trên nhãn và hạn dùng cùng chị."),
                                                                       (staff["name"], "Nếu bé có vấn đề sức khoẻ, chị hỏi thêm bác sĩ nhé.")],
         "Cận tay và nhãn sản phẩm, lấy nét nông", "Ánh sáng đều, không loá nhãn"),
        ("AN TÂM", f"{mom['name']} gật đầu, nét mặt nhẹ nhõm", [(mom["name"], "Được giải thích rõ ràng vậy, mình thấy an tâm hơn hẳn.")],
         "Cận trung, máy quay lia chậm", "Ánh sáng ấm, hậu cảnh mờ"),
        ("CTA", "Logo Ánh Ngân và slogan hiện trên nền cửa hàng", [(staff["name"], cta)],
         "Toàn cảnh mặt tiền cửa hàng, máy quay kéo lùi", "Ánh sáng ấm áp, thương hiệu rõ nét"),
    ]
    if n < len(beats):
        chosen = beats[: n - 1] + [beats[-1]] if n > 1 else [beats[0]]
    else:
        chosen = beats[:-1] + [beats[2]] * (n - len(beats)) + [beats[-1]]
    scenes = []
    for i, (stype, action, lines, camera, light) in enumerate(chosen):
        scenes.append({
            "title": f"Cảnh {i + 1}: {stype.title()}", "scene_type": stype, "action": action,
            "dialogue": [{"speaker": sp, "text": tx} for sp, tx in lines][:2], "setting": setting,
            "camera": camera, "lighting": light, "sound": "Tiếng nói rõ, nhạc nền nhẹ nhàng, tiếng cửa hàng rất nhỏ",
        })
    body = "\n".join(f"{s['title']} — {s['action']}. " + " ".join(f"{d['speaker']}: “{d['text']}”" for d in s["dialogue"]) for s in scenes)
    return {"title": idea["title"], "hook": idea["hook"], "body": body, "cta": cta, "scenes": scenes}


def build_user_prompt_ideas(brief: dict) -> str:
    return (f"Chủ đề: {brief['topic']}\nMục tiêu: {brief.get('objective', '')}\nKhách hàng mục tiêu: {brief.get('target_audience', '')}\n"
            f"Phong cách: {brief.get('style', '')}\nTrụ cột nội dung: {', '.join(brief.get('content_pillars', []))}\n"
            "Hãy đề xuất đúng 3 ý tưởng khác góc tiếp cận, mỗi ý tưởng có hook 3 giây (≤ 16 từ).")


def build_user_prompt_script(brief: dict, idea: dict, characters: list[dict], scene_seconds: int) -> str:
    n = max(1, math.ceil(brief["duration_sec"] / scene_seconds))
    chars = "; ".join(f"{c['name']} ({c.get('description', '')})" for c in characters) or "Mẹ Lan; Chị Ngân – tư vấn viên"
    return (f"Ý tưởng đã chọn: {idea['title']} — {idea.get('summary', '')}\nHook: {idea['hook']}\n"
            f"Nhân vật (giữ đúng tên): {chars}\nBối cảnh: {brief.get('setting', '')}\nCTA: {brief.get('cta', '')}\n"
            f"Viết kịch bản đúng {n} cảnh, mỗi cảnh {scene_seconds} giây, 1 hành động chính, tối đa 2 câu thoại.")
