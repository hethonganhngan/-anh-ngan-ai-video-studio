"""Lỗi interaction của Gemini (mảng `errors`): hết hạn mức → dừng chờ thao tác, không tự thử lại."""
from app.providers import google_genai as G
from app.providers.video.gemini_omni import GeminiOmniProvider, interaction_error

EXHAUSTED = {"status": "failed", "errors": [{"code": "RESOURCE_EXHAUSTED", "message": "There was a problem processing your request."}]}


def test_interaction_error_shapes():
    assert interaction_error(EXHAUSTED) == ("RESOURCE_EXHAUSTED", "There was a problem processing your request.")
    assert interaction_error({"error": "x"}) == (None, "x")
    assert interaction_error({}) == (None, None)


def test_quota_exhausted_needs_manual_action(monkeypatch):
    monkeypatch.setattr(G.GeminiClient, "request", lambda self, *a, **k: EXHAUSTED)
    st = GeminiOmniProvider("gemini_omni", "Omni", "k", {}).get_status("int:abc")
    assert st.state == "NEEDS_MANUAL_ACTION" and st.error_code == "QUOTA_EXHAUSTED" and "Billing" in st.error_message


def test_other_failure_keeps_code(monkeypatch):
    monkeypatch.setattr(G.GeminiClient, "request",
                        lambda self, *a, **k: {"status": "failed", "errors": [{"code": "SAFETY", "message": "blocked"}]})
    st = GeminiOmniProvider("gemini_omni", "Omni", "k", {}).get_status("int:abc")
    assert st.state == "FAILED" and st.error_code == "SAFETY" and st.error_message == "blocked"
