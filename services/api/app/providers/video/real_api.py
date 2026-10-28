"""RealAPIProvider — adapter cho API video CHÍNH THỨC (ví dụ Veo trên Vertex AI / Gemini API, Runway, Kling...).

Trạng thái: CHƯA KẾT NỐI. Adapter cấu hình qua M15 → API Connections (provider_accounts):
  config = {
    "submit_url": "https://.../generate",            # POST, body JSON theo body_template
    "status_url": "https://.../operations/{job_id}", # GET
    "auth_header": "Authorization", "auth_prefix": "Bearer ",
    "job_id_path": "name", "state_path": "done", "result_url_path": "response.videos.0.uri",
    "error_path": "error.message", "unit_cost_vnd_per_sec": 0, "max_duration_sec": 8,
    "body_template": {"prompt": "{prompt}", "negativePrompt": "{negative_prompt}", "durationSeconds": "{duration}",
                      "aspectRatio": "{aspect_ratio}"}
  }
Chỉ xác nhận "đã kết nối" sau khi chạy kiểm tra bằng key hợp lệ (connection_status = VERIFIED).
Không dùng cookie/token phiên đăng nhập hay endpoint không công khai.
"""
import json
import tempfile
from decimal import Decimal

import httpx
from app.providers.video.base import GenerationSpec, ProviderError, ProviderStatus, VideoProvider


def _dig(data, path: str):
    cur = data
    for part in path.split("."):
        if isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _fill(template, values: dict):
    if isinstance(template, dict):
        return {k: _fill(v, values) for k, v in template.items()}
    if isinstance(template, list):
        return [_fill(v, values) for v in template]
    if isinstance(template, str):
        for k, v in values.items():
            if template == "{" + k + "}":
                return v
            template = template.replace("{" + k + "}", str(v))
    return template


class RealAPIProvider(VideoProvider):
    kind = "REAL_API"
    is_real = True

    def __init__(self, code: str, name: str, api_key: str | None, config: dict, timeout: float = 60.0):
        self.code = code
        self.name = name
        self.api_key = api_key
        self.config = config or {}
        self.timeout = timeout
        self.unit_cost_vnd_per_sec = Decimal(str(self.config.get("unit_cost_vnd_per_sec", 0)))
        self.max_duration_sec = int(self.config.get("max_duration_sec", 8))
        self.supported_aspects = tuple(self.config.get("supported_aspects", ["9:16"]))

    def _require_config(self):
        if not self.api_key:
            raise ProviderError(f"{self.name}: chưa cấu hình API key", code="NOT_CONFIGURED", retryable=False)
        for k in ("submit_url", "status_url", "job_id_path", "state_path", "result_url_path"):
            if not self.config.get(k):
                raise ProviderError(f"{self.name}: thiếu cấu hình '{k}'", code="NOT_CONFIGURED", retryable=False)

    def _headers(self):
        return {self.config.get("auth_header", "Authorization"): f"{self.config.get('auth_prefix', 'Bearer ')}{self.api_key}",
                "Content-Type": "application/json"}

    def _request(self, method: str, url: str, **kw):
        try:
            r = httpx.request(method, url, headers=self._headers(), timeout=self.timeout, **kw)
        except httpx.TimeoutException:
            raise ProviderError(f"{self.name}: timeout", code="TIMEOUT", retryable=True)
        except httpx.HTTPError as e:
            raise ProviderError(f"{self.name}: không kết nối được ({e})", code="PROVIDER_UNAVAILABLE", retryable=True)
        if r.status_code in (401, 403):
            raise ProviderError(f"{self.name}: bị từ chối quyền ({r.status_code})", code="AUTH_FAILED", retryable=False)
        if r.status_code == 429:
            raise ProviderError(f"{self.name}: vượt hạn mức gọi API", code="RATE_LIMITED", retryable=True)
        if r.status_code >= 500:
            raise ProviderError(f"{self.name}: lỗi máy chủ {r.status_code}", code="PROVIDER_ERROR", retryable=True)
        if r.status_code >= 400:
            raise ProviderError(f"{self.name}: lỗi {r.status_code}: {r.text[:300]}", code="BAD_REQUEST", retryable=False)
        return r

    def submit_generation(self, spec: GenerationSpec) -> str:
        self._require_config()
        body = _fill(self.config.get("body_template", {"prompt": "{prompt}"}), {
            "prompt": spec.prompt_text, "negative_prompt": spec.negative_prompt, "duration": spec.duration_sec,
            "aspect_ratio": spec.aspect_ratio, "seed": spec.seed or 0,
        })
        data = self._request("POST", self.config["submit_url"], content=json.dumps(body)).json()
        job_id = _dig(data, self.config["job_id_path"])
        if not job_id:
            raise ProviderError(f"{self.name}: phản hồi không có job id", code="BAD_RESPONSE", retryable=False)
        return str(job_id)

    def get_status(self, provider_job_id: str) -> ProviderStatus:
        self._require_config()
        data = self._request("GET", self.config["status_url"].replace("{job_id}", provider_job_id)).json()
        err = _dig(data, self.config.get("error_path", "error.message"))
        if err:
            return ProviderStatus(state="FAILED", error_code="PROVIDER_FAILED", error_message=str(err)[:500])
        done = _dig(data, self.config["state_path"])
        succeeded_values = self.config.get("succeeded_values", [True, "SUCCEEDED", "succeeded", "COMPLETED"])
        return ProviderStatus(state="SUCCEEDED" if done in succeeded_values else "RUNNING", progress=100 if done else 50)

    def get_result(self, provider_job_id: str) -> str:
        self._require_config()
        data = self._request("GET", self.config["status_url"].replace("{job_id}", provider_job_id)).json()
        url = _dig(data, self.config["result_url_path"])
        if not url:
            raise ProviderError(f"{self.name}: chưa có URL kết quả", code="NOT_READY", retryable=True)
        fd, path = tempfile.mkstemp(suffix=".mp4")
        with httpx.stream("GET", url, headers=self._headers(), timeout=self.timeout * 5) as r, open(fd, "wb") as f:
            if r.status_code >= 400:
                raise ProviderError(f"{self.name}: tải kết quả lỗi {r.status_code}", code="DOWNLOAD_FAILED")
            for chunk in r.iter_bytes():
                f.write(chunk)
        return path

    def cancel_job(self, provider_job_id: str) -> bool:
        url = self.config.get("cancel_url")
        if not url:
            return False
        self._request("POST", url.replace("{job_id}", provider_job_id))
        return True
