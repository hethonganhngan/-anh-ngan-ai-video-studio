"""AnthropicProvider với máy chủ giả lập (không gọi API thật, không cần key thật)."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from app.providers.llm.base import LLMError

IDEAS = {"ideas": [{"title": f"Ý tưởng {i}", "angle": "QA", "hook": "Mẹ đã hỏi điều này chưa?", "summary": "Tóm tắt"} for i in range(3)]}


def _message(stop_reason="end_turn", text=json.dumps(IDEAS, ensure_ascii=False), stop_details=None):
    return {"id": "msg_test", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
            "content": [{"type": "thinking", "thinking": "", "signature": "sig"}, {"type": "text", "text": text}],
            "stop_reason": stop_reason, "stop_sequence": None, "stop_details": stop_details,
            "usage": {"input_tokens": 1000, "output_tokens": 500}}


@pytest.fixture
def fake_api(monkeypatch):
    state = {"response": _message(), "status": 200, "requests": []}

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["content-length"])))
            state["requests"].append({"path": self.path, "headers": dict(self.headers), "body": body})
            payload = json.dumps(state["response"]).encode()
            self.send_response(state["status"])
            self.send_header("content-type", "application/json")
            self.send_header("request-id", "req_test")
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("ANTHROPIC_BASE_URL", f"http://127.0.0.1:{srv.server_port}")
    yield state
    srv.shutdown()


def _provider():
    from app.providers.llm.anthropic_provider import AnthropicProvider

    p = AnthropicProvider(api_key="sk-ant-test", model="claude-opus-5-5")
    p.client = p.client.with_options(max_retries=0)
    return p


def test_ideas_json_and_request_shape(fake_api):
    from app.agents.roles.script_agent import IDEA_SCHEMA

    res = _provider().complete_json(system="sys", prompt="Chủ đề: chọn sữa", schema=IDEA_SCHEMA)
    assert res.data == IDEAS and not res.simulated
    assert res.input_tokens == 1000 and res.output_tokens == 500 and res.cost_vnd > 0
    req = fake_api["requests"][0]
    assert req["path"].startswith("/v1/messages")
    assert "server-side-fallback-2026-07-01" in req["headers"].get("anthropic-beta", "")
    b = req["body"]
    assert b["model"] == "claude-opus-5-5" and b["fallbacks"] == "default" and b["max_tokens"] == 16000
    assert b["output_config"]["format"] == {"type": "json_schema", "schema": IDEA_SCHEMA}
    assert "thinking" not in b and "temperature" not in b


def test_refusal_raises(fake_api):
    fake_api["response"] = _message(stop_reason="refusal", text="",
                                    stop_details={"type": "refusal", "category": None, "explanation": None})
    with pytest.raises(LLMError) as e:
        _provider().complete_json(system="s", prompt="p", schema={"type": "object"})
    assert e.value.code == "REFUSAL"


def test_auth_error(fake_api):
    fake_api["status"] = 401
    fake_api["response"] = {"type": "error", "error": {"type": "authentication_error", "message": "invalid x-api-key"}}
    with pytest.raises(LLMError) as e:
        _provider().complete_json(system="s", prompt="p", schema={"type": "object"})
    assert e.value.code == "AUTH_FAILED"
