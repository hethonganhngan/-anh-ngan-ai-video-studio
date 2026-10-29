"""Adapter Gemini (Omni video + TTS): dựng request, đọc phản hồi, chạy nền / dự phòng đồng bộ — giả lập HTTP."""
import base64
import io
import wave

import pytest
from app.providers import google_genai as G
from app.providers.tts.base import TTSRequest
from app.providers.tts.gemini_tts import GeminiTTSProvider
from app.providers.video.base import GenerationSpec, ProviderError
from app.providers.video.gemini_omni import NO_SPEECH, GeminiOmniProvider


def _out(kind, **item):
    return {"id": "int-1", "status": "completed", "steps": [{"type": "model_output", "content": [{"type": kind, **item}]}]}


def test_omni_prompt_and_body():
    p = GeminiOmniProvider("gemini_omni", "Omni", "k", {"resolution": "1080p"})
    spec = GenerationSpec(job_ref="j", prompt_text="Mẹ bế bé trong cửa hàng", negative_prompt="logo đối thủ",
                          duration_sec=8, aspect_ratio="9:16")
    body = p.build_body(spec, background=True)
    assert body["model"] == "gemini-omni-1.1-flash" and body["background"] is True
    assert body["response_format"] == {"type": "video", "aspect_ratio": "9:16", "resolution": "1080p"}
    assert "Tránh: logo đối thủ" in body["input"] and NO_SPEECH in body["input"]
    assert p.build_body(spec, background=False)["response_format"]["delivery"] == "uri"


def test_omni_background_flow(monkeypatch):
    calls = []

    def fake(self, method, path, json=None, timeout=None):
        calls.append((method, path))
        if method == "POST":
            return {"id": "abc", "status": "in_progress"}
        return _out("video", data=base64.b64encode(b"\x00\x00\x00\x18ftypmp42").decode())

    monkeypatch.setattr(G.GeminiClient, "request", fake)
    p = GeminiOmniProvider("gemini_omni", "Omni", "k", {})
    jid = p.submit_generation(GenerationSpec(job_ref="j", prompt_text="x"))
    assert jid == "int:abc"
    assert p.get_status(jid).state == "SUCCEEDED"
    with open(p.get_result(jid), "rb") as f:
        assert f.read()[4:8] == b"ftyp"
    assert ("GET", "interactions/abc") in calls


def test_omni_falls_back_to_sync(monkeypatch):
    def fake(self, method, path, json=None, timeout=None):
        if method == "POST" and json.get("background"):
            raise G.GeminiError("background is not supported for this model", code="BAD_REQUEST", retryable=False, status=400)
        if method == "POST":
            return _out("video", uri="https://generativelanguage.googleapis.com/v1beta/files/f123:download?alt=media")
        return {"state": "ACTIVE"}

    monkeypatch.setattr(G.GeminiClient, "request", fake)
    p = GeminiOmniProvider("gemini_omni", "Omni", "k", {})
    jid = p.submit_generation(GenerationSpec(job_ref="j", prompt_text="x"))
    assert jid == "file:files/f123"
    assert p.get_status(jid).state == "SUCCEEDED"


def test_omni_errors_map_to_provider_error(monkeypatch):
    def fake(self, *a, **k):
        raise G.GeminiError("Gemini từ chối quyền (403)", code="AUTH_FAILED", retryable=False, status=403)

    monkeypatch.setattr(G.GeminiClient, "request", fake)
    with pytest.raises(ProviderError) as e:
        GeminiOmniProvider("gemini_omni", "Omni", "k", {}).submit_generation(GenerationSpec(job_ref="j", prompt_text="x"))
    assert e.value.code == "AUTH_FAILED" and e.value.retryable is False
    with pytest.raises(ProviderError):
        GeminiOmniProvider("gemini_omni", "Omni", None, {}).submit_generation(GenerationSpec(job_ref="j", prompt_text="x"))


def test_tts_wav_and_raw_pcm(monkeypatch):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(b"\x00\x00" * 24000)
    payloads = [buf.getvalue(), b"\x00\x00" * 12000]
    sent = []

    def fake(self, method, path, json=None, timeout=None):
        sent.append(json)
        return _out("audio", data=base64.b64encode(payloads[len(sent) - 1]).decode())

    monkeypatch.setattr(G.GeminiClient, "request", fake)
    tts = GeminiTTSProvider(api_key="k", config={})
    r = tts.synthesize(TTSRequest(text="Xin chào mẹ", voice_id="Puck", style="Đọc bằng tiếng Việt, giọng Miền Trung"))
    assert r.duration_sec == 1.0 and r.simulated is False
    assert sent[0]["generation_config"]["speech_config"][0]["voice"] == "Puck"
    assert sent[0]["input"][0]["content"][0]["text"].endswith(": Xin chào mẹ")
    r2 = tts.synthesize(TTSRequest(text="Chào", voice_id="KhongCo"))
    assert r2.duration_sec == 0.5 and sent[1]["generation_config"]["speech_config"][0]["voice"] == "Kore"


def test_download_never_sends_key_to_other_hosts(monkeypatch, tmp_path):
    seen = []

    class Resp:
        def __init__(self, status, headers=None, body=b""):
            self.status_code, self.headers, self._b = status, headers or {}, body

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def iter_bytes(self):
            yield self._b

        def read(self):
            return self._b

    def fake_stream(method, url, headers=None, **kw):
        seen.append((url, dict(headers or {})))
        if "generativelanguage" in url:
            return Resp(302, {"location": "https://storage.googleusercontent.com/v?sig=1"})
        return Resp(200, body=b"video")

    monkeypatch.setattr(G.httpx, "stream", fake_stream)
    G.GeminiClient("secret").download("files/abc", str(tmp_path / "v.mp4"))
    assert seen[0][1].get("x-goog-api-key") == "secret"
    assert "x-goog-api-key" not in seen[1][1]
