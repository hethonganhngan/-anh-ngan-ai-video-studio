"""Google Veo trên Vertex AI — tạo video bằng API chính thức của Google Cloud (dùng được tín dụng dùng thử Google Cloud).

Tài liệu: https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/veo-video-generation
- Gửi: POST .../publishers/google/models/{model}:predictLongRunning → provider_job_id = tên operation.
- Poll/kết quả: POST .../models/{model}:fetchPredictOperation {"operationName"} → video base64 (không dùng GCS).
Xác thực: "API key" của provider là nội dung file JSON service account (quyền Vertex AI User); access token
OAuth2 ký RS256 bằng private key, chỉ gửi tới *.googleapis.com. Chỉ VERIFIED sau khi M15 → Test thành công.
"""
import base64
import json
import mimetypes
import re
import tempfile
import threading
import time
from decimal import Decimal

import httpx
import jwt
from app.providers.video.base import GenerationSpec, ProviderError, ProviderStatus, VideoProvider

DEFAULT_MODEL = "veo-3.1-fast-generate-001"
DEFAULT_LOCATION = "us-central1"
SCOPE = "https://www.googleapis.com/auth/cloud-platform"
DURATIONS = (4, 6, 8)
NEGATIVE_LINE = re.compile(r"^\[\d+\.\s*NEGATIVE PROMPT\].*$", re.MULTILINE)
# AI vẽ chữ tiếng Việt/logo rất kém → cấm chữ; logo & phụ đề chuẩn được ghép ở bước dựng (M06)
NO_TEXT = ("Không có bất kỳ chữ, logo, nhãn hiệu hay ký tự đọc được trong khung hình: biển hiệu, kệ hàng, bao bì, "
           "màn hình đều trơn hoặc mờ. No readable text, letters, logos or brand names anywhere in the frame; "
           "signage and product packaging are plain or blurred.")
SILENT_SPEECH = ("Nhân vật nói chuyện với khẩu hình tự nhiên theo lời thoại, nhưng video không có tiếng nói "
                 "(giọng đọc được lồng sau). The character speaks naturally with lip movement; no audible voice.")
MAX_REFS = 3

_tokens: dict[str, tuple[str, float]] = {}
_lock = threading.Lock()


def parse_service_account(raw: str | None) -> dict:
    if not raw:
        raise ProviderError("Chưa nạp file khoá service account (JSON) cho Vertex AI", code="NOT_CONFIGURED", retryable=False)
    try:
        sa = json.loads(raw)
    except ValueError:
        raise ProviderError("Khoá Vertex AI phải là nội dung file JSON service account", code="NOT_CONFIGURED", retryable=False)
    missing = [k for k in ("client_email", "private_key", "project_id") if not sa.get(k)]
    if sa.get("type") != "service_account" or missing:
        raise ProviderError(f"File JSON không phải khoá service account hợp lệ (thiếu {', '.join(missing) or 'type'})",
                            code="NOT_CONFIGURED", retryable=False)
    return sa


class VeoVertexProvider(VideoProvider):
    kind = "REAL_API"
    is_real = True
    supported_aspects = ("9:16", "16:9")
    max_duration_sec = 8

    def __init__(self, code: str, name: str, api_key: str | None, config: dict, unit_cost_vnd_per_sec=0,
                 timeout: float = 60.0):
        self.code = code
        self.name = name
        self.config = config or {}
        self.credentials = api_key
        self.timeout = timeout
        self.model = self.config.get("model", DEFAULT_MODEL)
        self.location = self.config.get("location", DEFAULT_LOCATION)
        self.resolution = self.config.get("resolution", "720p")
        # speech_in_video=False: thoại do TTS giọng M04 lồng ở bước dựng → Veo tạo video không tiếng
        self.speech_in_video = bool(self.config.get("speech_in_video", True))
        self.generate_audio = bool(self.config.get("generate_audio", True)) and self.speech_in_video
        self.unit_cost_vnd_per_sec = Decimal(str(unit_cost_vnd_per_sec or self.config.get("unit_cost_vnd_per_sec", 0)))

    # ---------- xác thực ----------
    def _sa(self) -> dict:
        return parse_service_account(self.credentials)

    def _token(self) -> str:
        sa = self._sa()
        with _lock:
            tok, exp = _tokens.get(sa["client_email"], ("", 0.0))
            if tok and exp - time.time() > 300:
                return tok
        now = int(time.time())
        token_uri = sa.get("token_uri", "https://oauth2.googleapis.com/token")
        try:
            assertion = jwt.encode({"iss": sa["client_email"], "scope": SCOPE, "aud": token_uri, "iat": now, "exp": now + 3600},
                                   sa["private_key"], algorithm="RS256", headers={"kid": sa.get("private_key_id", "")})
        except Exception as e:  # noqa: BLE001 — khoá hỏng
            raise ProviderError(f"Không ký được token bằng private key: {e}", code="NOT_CONFIGURED", retryable=False)
        try:
            r = httpx.post(token_uri, data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion},
                           timeout=self.timeout)
        except httpx.HTTPError as e:
            raise ProviderError(f"Vertex AI: không lấy được access token ({e})", code="PROVIDER_UNAVAILABLE", retryable=True)
        if r.status_code >= 400:
            raise ProviderError(f"Google từ chối service account: {r.text[:300]}", code="AUTH_FAILED", retryable=False)
        data = r.json()
        with _lock:
            _tokens[sa["client_email"]] = (data["access_token"], time.time() + int(data.get("expires_in", 3600)))
        return data["access_token"]

    def _call(self, method: str, url: str, body: dict | None = None, timeout: float | None = None) -> dict:
        if not re.match(r"^https://[a-z0-9-]+\.googleapis\.com/", url):
            raise ProviderError("Chỉ gửi token tới *.googleapis.com", code="BAD_URL", retryable=False)
        try:
            r = httpx.request(method, url, json=body, timeout=timeout or self.timeout,
                              headers={"Authorization": f"Bearer {self._token()}", "Content-Type": "application/json"})
        except httpx.TimeoutException:
            raise ProviderError("Vertex AI: hết thời gian chờ", code="TIMEOUT", retryable=True)
        except httpx.HTTPError as e:
            raise ProviderError(f"Vertex AI: không kết nối được ({e})", code="PROVIDER_UNAVAILABLE", retryable=True)
        if r.status_code >= 400:
            raise _http_error(r)
        return r.json() if r.content else {}

    def _model_url(self) -> str:
        project = self._sa()["project_id"]
        return (f"https://{self.location}-aiplatform.googleapis.com/v1/projects/{project}/locations/{self.location}"
                f"/publishers/google/models/{self.model}")

    # ---------- VideoProvider ----------
    def build_body(self, spec: GenerationSpec) -> dict:
        prompt = NEGATIVE_LINE.sub("", spec.prompt_text).strip()  # negative đi qua tham số riêng của Veo
        prompt = "\n\n".join([prompt, NO_TEXT] + ([] if self.speech_in_video else [SILENT_SPEECH]))
        instance: dict = {"prompt": prompt}
        refs = [p for p in spec.reference_image_paths if p][:MAX_REFS]
        if refs:  # ảnh tham chiếu "asset" của Character Lock → giữ mặt & trang phục đồng nhất giữa các cảnh
            instance["referenceImages"] = [{"image": _image(p), "referenceType": "asset"} for p in refs]
        duration = 8 if refs else min(DURATIONS, key=lambda d: (abs(d - spec.duration_sec), -d))
        params = {"aspectRatio": spec.aspect_ratio, "durationSeconds": duration, "sampleCount": 1,
                  "resolution": self.resolution, "generateAudio": self.generate_audio, "personGeneration": "allow_adult"}
        if spec.negative_prompt:
            params["negativePrompt"] = spec.negative_prompt.strip()
        if spec.seed is not None:
            params["seed"] = spec.seed
        return {"instances": [instance], "parameters": params}

    def submit_generation(self, spec: GenerationSpec) -> str:
        data = self._call("POST", f"{self._model_url()}:predictLongRunning", self.build_body(spec))
        if not data.get("name"):
            raise ProviderError(f"{self.name}: phản hồi không có operation", code="BAD_RESPONSE", retryable=False)
        return data["name"]

    def _operation(self, name: str) -> dict:
        return self._call("POST", f"{self._model_url()}:fetchPredictOperation", {"operationName": name}, timeout=120)

    def get_status(self, provider_job_id: str) -> ProviderStatus:
        op = self._operation(provider_job_id)
        if not op.get("done"):
            return ProviderStatus(state="RUNNING", progress=50)
        if op.get("error"):
            err = op["error"]
            return ProviderStatus(state="FAILED", error_code=str(err.get("status") or err.get("code") or "PROVIDER_FAILED"),
                                  error_message=(err.get("message") or "Veo báo lỗi")[:500])
        res = op.get("response") or {}
        if not res.get("videos"):
            if res.get("raiMediaFilteredCount"):
                reasons = "; ".join(res.get("raiMediaFilteredReasons") or [])
                return ProviderStatus(state="NEEDS_MANUAL_ACTION", error_code="SAFETY_FILTERED",
                                      error_message=f"Google chặn video do bộ lọc an toàn — sửa prompt cảnh rồi tạo lại. {reasons}"[:500])
            return ProviderStatus(state="FAILED", error_code="BAD_RESPONSE", error_message="Veo hoàn tất nhưng không có video")
        return ProviderStatus(state="SUCCEEDED", progress=100)

    def get_result(self, provider_job_id: str) -> str:
        videos = (self._operation(provider_job_id).get("response") or {}).get("videos") or []
        b64 = videos[0].get("bytesBase64Encoded") if videos else None
        if not b64:
            raise ProviderError(f"{self.name}: không có dữ liệu video (cấu hình không được đặt storageUri)",
                                code="NOT_READY", retryable=True)
        fd, path = tempfile.mkstemp(suffix=".mp4")
        with open(fd, "wb") as f:
            f.write(base64.b64decode(b64))
        return path

    def cancel_job(self, provider_job_id: str) -> bool:
        return False  # Veo không có API huỷ operation tạo video; huỷ trong app chỉ bỏ theo dõi

    def test_connection(self) -> str:
        """Lấy access token + đọc thông tin model — không tạo video nên không tốn phí."""
        info = self._call("GET", f"https://{self.location}-aiplatform.googleapis.com/v1beta1/publishers/google/models/{self.model}")
        return f"{self._sa()['project_id']} · {info.get('name', self.model)}"


def _image(path: str) -> dict:
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    return {"bytesBase64Encoded": data, "mimeType": mimetypes.guess_type(path)[0] or "image/jpeg"}


def _http_error(r: httpx.Response) -> ProviderError:
    try:
        err = r.json().get("error", {})
    except ValueError:
        err = {}
    status, msg = err.get("status", ""), (err.get("message") or r.text)[:400]
    if r.status_code == 429 or status == "RESOURCE_EXHAUSTED":
        return ProviderError(f"Vertex AI hết hạn mức: {msg}", code="QUOTA_EXHAUSTED", retryable=True)
    if r.status_code in (401, 403):
        return ProviderError(f"Vertex AI từ chối quyền (bật Vertex AI API, Billing/tín dụng dùng thử, "
                             f"cấp vai trò Vertex AI User cho service account): {msg}", code="PERMISSION_DENIED", retryable=False)
    if r.status_code == 404:
        return ProviderError(f"Không thấy model/operation (kiểm tra 'model' và 'location' ở M15): {msg}",
                             code="NOT_FOUND", retryable=False)
    return ProviderError(f"Vertex AI lỗi {r.status_code}: {msg}", code=status or f"HTTP_{r.status_code}",
                         retryable=r.status_code >= 500)
