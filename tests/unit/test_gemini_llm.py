"""Gemini LLM (A02/A08/A09): structured output, đọc usage/chi phí, dự phòng system_instruction, lỗi — giả lập HTTP."""
import json

import pytest
from app.providers import google_genai as G
from app.providers.llm.base import LLMError
from app.providers.llm.gemini_provider import GeminiLLMProvider

SCHEMA = {"type": "object", "properties": {"title": {"type": "string"}}, "required": ["title"]}


def _resp(text, **usage):
    return {"id": "i1", "status": "completed", "model": "gemini-3.8-flash", "usage": usage,
            "steps": [{"type": "user_input", "content": [{"type": "text", "text": "bỏ qua"}]},
                      {"type": "model_output", "content": [{"type": "text", "text": text[:5]}, {"type": "text", "text": text[5:]}]}]}


def test_structured_output_and_cost(monkeypatch):
    sent = []

    def fake(self, method, path, json=None, timeout=None):
        sent.append(json)
        return _resp('{"title": "Chọn sữa cho bé"}', total_input_tokens=1000, total_output_tokens=500, total_thought_tokens=500)

    monkeypatch.setattr(G.GeminiClient, "request", fake)
    r = GeminiLLMProvider("k").complete_json(system="Bạn là A02", prompt="Viết kịch bản", schema=SCHEMA)
    assert r.data == {"title": "Chọn sữa cho bé"} and r.simulated is False and r.provider == "gemini"
    assert r.input_tokens == 1000 and r.output_tokens == 1000 and r.cost_vnd > 0
    b = sent[0]
    assert b["model"] == "gemini-3.8-flash" and b["system_instruction"] == "Bạn là A02" and b["input"] == "Viết kịch bản"
    assert b["response_format"] == {"type": "text", "mime_type": "application/json", "schema": SCHEMA}
    assert b["generation_config"]["max_output_tokens"] == 16000


def test_inline_system_fallback(monkeypatch):
    sent = []

    def fake(self, method, path, json=None, timeout=None):
        sent.append(json)
        if "system_instruction" in json:
            raise G.GeminiError("Unknown name \"system_instruction\"", code="BAD_REQUEST", retryable=False, status=400)
        return _resp('{"title": "ok"}')

    monkeypatch.setattr(G.GeminiClient, "request", fake)
    r = GeminiLLMProvider("k", model="gemini-4-argon").complete_json(system="SYS", prompt="P", schema=SCHEMA)
    assert r.data["title"] == "ok" and sent[1]["input"].startswith("SYS") and sent[1]["model"] == "gemini-4-argon"


@pytest.mark.parametrize("payload,code", [
    ({"status": "completed", "steps": []}, "REFUSAL"),
    (_resp("không phải json"), "INVALID_JSON"),
    ({"status": "failed", "error": "quota"}, "PROVIDER_ERROR"),
])
def test_bad_responses(monkeypatch, payload, code):
    monkeypatch.setattr(G.GeminiClient, "request", lambda self, *a, **k: json.loads(json.dumps(payload)))
    with pytest.raises(LLMError) as e:
        GeminiLLMProvider("k").complete_json(system="s", prompt="p", schema=SCHEMA)
    assert e.value.code == code


def test_auth_error_not_retryable(monkeypatch):
    def fake(self, *a, **k):
        raise G.GeminiError("Gemini từ chối quyền (403)", code="AUTH_FAILED", retryable=False, status=403)

    monkeypatch.setattr(G.GeminiClient, "request", fake)
    with pytest.raises(LLMError) as e:
        GeminiLLMProvider("k").complete_json(system="s", prompt="p", schema=SCHEMA)
    assert e.value.code == "AUTH_FAILED" and not e.value.retryable
    with pytest.raises(LLMError):
        GeminiLLMProvider("")
