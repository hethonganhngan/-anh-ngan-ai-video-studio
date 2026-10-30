"""Adapter Veo trên Vertex AI: service account → token, dựng request, poll operation, bộ lọc an toàn — giả lập HTTP."""
import base64
import json

import httpx
import jwt
import pytest
from app.providers.video import veo_vertex as V
from app.providers.video.base import GenerationSpec, ProviderError
from app.providers.video.veo_vertex import VeoVertexProvider
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PEM = KEY.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
SA = json.dumps({"type": "service_account", "project_id": "anngan-video", "private_key_id": "kid1", "private_key": PEM,
                 "client_email": "veo@anngan-video.iam.gserviceaccount.com", "token_uri": "https://oauth2.googleapis.com/token"})
PROMPT = "[1. LOẠI CẢNH] Talking Head\n[3. HÀNH ĐỘNG] Mẹ Ánh Ngân chào\n[9. NEGATIVE PROMPT] logo sai\nĐịnh dạng: video dọc 9:16"
MP4 = b"\x00\x00\x00\x18ftypmp42"


def _resp(status: int, body: dict) -> httpx.Response:
    return httpx.Response(status, json=body, request=httpx.Request("POST", "https://x.googleapis.com"))


@pytest.fixture
def fake_google(monkeypatch):
    V._tokens.clear()
    calls = []

    def post(url, data=None, timeout=None):
        claims = jwt.decode(data["assertion"], KEY.public_key(), algorithms=["RS256"], audience=url)
        assert claims["iss"] == "veo@anngan-video.iam.gserviceaccount.com" and "cloud-platform" in claims["scope"]
        calls.append(("TOKEN", url))
        return _resp(200, {"access_token": "tok", "expires_in": 3600})

    state = {"done": False, "response": {"videos": [{"bytesBase64Encoded": base64.b64encode(MP4).decode()}]}}

    def request(method, url, json=None, timeout=None, headers=None):
        assert headers["Authorization"] == "Bearer tok"
        calls.append((method, url, json))
        if url.endswith(":predictLongRunning"):
            return _resp(200, {"name": "projects/anngan-video/locations/us-central1/publishers/google/models/m/operations/op1"})
        if url.endswith(":fetchPredictOperation"):
            return _resp(200, {"name": json["operationName"], **({"done": True, "response": state["response"]} if state["done"] else {})})
        return _resp(200, {"name": "publishers/google/models/veo-3.1-fast-generate-001"})

    monkeypatch.setattr(V.httpx, "post", post)
    monkeypatch.setattr(V.httpx, "request", request)
    return calls, state


def test_body_strips_negative_line_and_snaps_duration():
    p = VeoVertexProvider("veo_vertex", "Veo", SA, {"resolution": "1080p"})
    body = p.build_body(GenerationSpec(job_ref="j", prompt_text=PROMPT, negative_prompt="logo sai", duration_sec=7, aspect_ratio="9:16"))
    assert "NEGATIVE" not in body["instances"][0]["prompt"] and "Mẹ Ánh Ngân chào" in body["instances"][0]["prompt"]
    params = body["parameters"]
    assert params["negativePrompt"] == "logo sai" and params["durationSeconds"] == 8 and params["aspectRatio"] == "9:16"
    assert params["resolution"] == "1080p" and params["generateAudio"] is True and params["sampleCount"] == 1


def test_body_reference_images_no_text_and_silent_speech(tmp_path):
    imgs = []
    for i in range(4):
        f = tmp_path / f"ref{i}.jpg"
        f.write_bytes(b"\xff\xd8\xff" + bytes([i]))
        imgs.append(str(f))
    p = VeoVertexProvider("veo_vertex", "Veo", SA, {"speech_in_video": False, "generate_audio": True})
    body = p.build_body(GenerationSpec(job_ref="j", prompt_text=PROMPT, duration_sec=6, reference_image_paths=imgs))
    inst, params = body["instances"][0], body["parameters"]
    assert len(inst["referenceImages"]) == 3 and all(r["referenceType"] == "asset" for r in inst["referenceImages"])
    assert inst["referenceImages"][0]["image"] == {"bytesBase64Encoded": base64.b64encode(b"\xff\xd8\xff\x00").decode(),
                                                   "mimeType": "image/jpeg"}
    assert V.NO_TEXT in inst["prompt"] and V.SILENT_SPEECH in inst["prompt"]
    assert params["generateAudio"] is False and params["durationSeconds"] == 8  # ảnh tham chiếu: Veo yêu cầu 8 giây
    talking = VeoVertexProvider("veo_vertex", "Veo", SA, {}).build_body(GenerationSpec(job_ref="j", prompt_text=PROMPT))
    assert "referenceImages" not in talking["instances"][0] and V.SILENT_SPEECH not in talking["instances"][0]["prompt"]
    assert talking["parameters"]["generateAudio"] is True


def test_submit_poll_download(fake_google):
    calls, state = fake_google
    p = VeoVertexProvider("veo_vertex", "Veo", SA, {})
    jid = p.submit_generation(GenerationSpec(job_ref="j", prompt_text=PROMPT))
    assert jid.endswith("/operations/op1")
    assert calls[1][1] == ("https://us-central1-aiplatform.googleapis.com/v1/projects/anngan-video/locations/us-central1"
                           "/publishers/google/models/veo-3.1-fast-generate-001:predictLongRunning")
    assert p.get_status(jid).state == "RUNNING"
    state["done"] = True
    assert p.get_status(jid).state == "SUCCEEDED"
    with open(p.get_result(jid), "rb") as f:
        assert f.read() == MP4
    assert sum(1 for c in calls if c[0] == "TOKEN") == 1  # token được dùng lại
    assert "anngan-video" in p.test_connection()


def test_safety_filter_needs_manual(fake_google):
    _, state = fake_google
    state.update(done=True, response={"raiMediaFilteredCount": 1, "raiMediaFilteredReasons": ["child safety"]})
    st = VeoVertexProvider("veo_vertex", "Veo", SA, {}).get_status("op")
    assert st.state == "NEEDS_MANUAL_ACTION" and st.error_code == "SAFETY_FILTERED" and "child safety" in st.error_message


def test_permission_error_not_retryable(fake_google, monkeypatch):
    monkeypatch.setattr(V.httpx, "request", lambda *a, **k: _resp(403, {"error": {"status": "PERMISSION_DENIED", "message": "billing"}}))
    with pytest.raises(ProviderError) as e:
        VeoVertexProvider("veo_vertex", "Veo", SA, {}).submit_generation(GenerationSpec(job_ref="j", prompt_text="x"))
    assert e.value.code == "PERMISSION_DENIED" and e.value.retryable is False


@pytest.mark.parametrize("raw", [None, "not json", json.dumps({"type": "service_account", "project_id": "p"})])
def test_bad_credentials(raw):
    with pytest.raises(ProviderError) as e:
        VeoVertexProvider("veo_vertex", "Veo", raw, {}).submit_generation(GenerationSpec(job_ref="j", prompt_text="x"))
    assert e.value.code == "NOT_CONFIGURED"
