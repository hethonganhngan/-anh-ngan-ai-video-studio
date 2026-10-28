"""Kiểm tra storyboard theo chuẩn: 9:16, cảnh 8 giây, 1 hành động chính, ≤ 2 câu thoại."""
import re

MULTI_ACTION = re.compile(r"\b(rồi|sau đó|tiếp theo|đồng thời|xong)\b", re.IGNORECASE)


def validate_scenes(scenes: list[dict], *, scene_seconds: int = 8, max_dialogue: int = 2) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    if not scenes:
        errors.append("Storyboard chưa có cảnh nào")
    for i, s in enumerate(scenes, start=1):
        label = f"Cảnh {i}"
        action = (s.get("action") or "").strip()
        if not action:
            errors.append(f"{label}: thiếu hành động chính")
        elif MULTI_ACTION.search(action) or action.count(".") > 1:
            warnings.append(f"{label}: có vẻ nhiều hơn 1 hành động chính — nên tách cảnh")
        dialogue = s.get("dialogue") or []
        if len(dialogue) > max_dialogue:
            errors.append(f"{label}: {len(dialogue)} câu thoại, tối đa {max_dialogue}")
        for d in dialogue:
            text = (d.get("text") if isinstance(d, dict) else str(d)) or ""
            if len(text) > 160:
                errors.append(f"{label}: câu thoại quá dài ({len(text)} ký tự, tối đa 160)")
            words = len(text.split())
            if words > 28:
                warnings.append(f"{label}: câu thoại {words} từ có thể không vừa {scene_seconds} giây")
        dur = int(s.get("duration_sec") or scene_seconds)
        if dur > scene_seconds:
            errors.append(f"{label}: {dur}s vượt chuẩn {scene_seconds}s/cảnh")
        elif dur != scene_seconds:
            warnings.append(f"{label}: {dur}s khác mục tiêu {scene_seconds}s")
    return errors, warnings
