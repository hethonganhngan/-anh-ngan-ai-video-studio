"""D24: mô tả bài đăng luôn có ghi chú 'nhân vật minh hoạ' (nhân vật AI), không thêm trùng."""
from app.modules.publishing.service import AI_LABEL, with_ai_label


def test_label_appended_once():
    out = with_ai_label("Mẹ chọn sữa cho bé 3 tuổi nè")
    assert out.endswith(AI_LABEL) and out.startswith("Mẹ chọn sữa")
    assert with_ai_label(out) == out
    assert with_ai_label("") == AI_LABEL
    assert with_ai_label("Video có nhân vật minh họa") == "Video có nhân vật minh họa"
