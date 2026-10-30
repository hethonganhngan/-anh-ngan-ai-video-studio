"""VieNeu-TTS (giọng nhân bản chạy trên máy): tự nạp giọng mẫu khi máy chủ chưa có, PCM → WAV, chỉ gọi localhost."""
import wave

import httpx
import pytest
from app.providers.tts import vieneu_local as V
from app.providers.tts.base import TTSError, TTSRequest
from app.providers.tts.vieneu_local import VieNeuLocalProvider

from tests.helpers import make_audio

PCM_1S = b"\x01\x00" * V.SAMPLE_RATE


def _resp(status, content=b"", text=""):
    return httpx.Response(status, content=content or text.encode(), request=httpx.Request("POST", "http://127.0.0.1:8200"))


@pytest.fixture
def server(monkeypatch):
    state = {"voices": set(), "calls": []}

    def post(url, timeout=None, json=None, data=None, files=None):
        state["calls"].append(url.rsplit("/", 1)[-1])
        if url.endswith("/v1/voices"):
            assert files["file"][1].read(4) == b"RIFF" and data["name"] == "VOI-2610-0004"
            state["voices"].add(data["name"])
            return _resp(200, text='{"id": "VOI-2610-0004"}')
        if json["voice"] not in state["voices"]:
            return _resp(400, text=f"unknown voice '{json['voice']}'; see GET /v1/voices")
        assert json["response_format"] == "pcm" and json["sample_rate"] == V.SAMPLE_RATE
        return _resp(200, content=PCM_1S)

    monkeypatch.setattr(V.httpx, "post", post)
    return state


def test_enrolls_reference_once_then_speaks(server):
    ref = str(make_audio("chinh_chu.mp3", seconds=12))
    p = VieNeuLocalProvider()
    r = p.synthesize(TTSRequest(text="Chào cả nhà", voice_id="VOI-2610-0004", reference_audio_path=ref))
    assert r.duration_sec == 1.0 and not r.simulated and r.meta["voice"] == "VOI-2610-0004"
    with wave.open(r.path, "rb") as w:
        assert w.getframerate() == V.SAMPLE_RATE and w.getnframes() == V.SAMPLE_RATE
    p.synthesize(TTSRequest(text="Câu thứ hai", voice_id="VOI-2610-0004", reference_audio_path=ref))
    assert server["calls"] == ["speech", "voices", "speech", "speech"]  # chỉ nạp giọng mẫu 1 lần
    assert p.estimate_cost_vnd("Chào cả nhà") == 0


def test_unknown_voice_without_reference_errors(server):
    with pytest.raises(TTSError) as e:
        VieNeuLocalProvider().synthesize(TTSRequest(text="x", voice_id="VOI-2610-0004"))
    assert e.value.code == "NO_REFERENCE"


def test_only_localhost():
    with pytest.raises(TTSError) as e:
        VieNeuLocalProvider({"base_url": "http://10.0.0.2:8200"}).synthesize(TTSRequest(text="x", voice_id="v"))
    assert e.value.code == "BAD_URL"


def test_server_down_is_retryable(monkeypatch):
    def down(*a, **k):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(V.httpx, "post", down)
    with pytest.raises(TTSError) as e:
        VieNeuLocalProvider().synthesize(TTSRequest(text="x", voice_id="v"))
    assert e.value.code == "PROVIDER_UNAVAILABLE" and e.value.retryable and "start-vieneu.ps1" in str(e.value)
