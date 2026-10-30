"""Client REST tối giản cho Gemini API (Interactions API) — dùng chung cho video (Gemini Omni) và TTS.

Tài liệu: https://ai.google.dev/gemini-api/docs/omni · /speech-generation · /background-execution
Xác thực bằng header `x-goog-api-key`. Key chỉ gửi tới generativelanguage.googleapis.com.
"""
import base64
from urllib.parse import urljoin, urlparse

import httpx

BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
API_HOST = urlparse(BASE_URL).hostname
API_REVISION = "2026-05-20"


class GeminiError(Exception):
    def __init__(self, message: str, code: str = "PROVIDER_ERROR", retryable: bool = True, status: int | None = None):
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.status = status


class GeminiClient:
    def __init__(self, api_key: str, timeout: float = 60.0):
        if not api_key:
            raise GeminiError("Chưa cấu hình API key Gemini", code="NOT_CONFIGURED", retryable=False)
        self.api_key = api_key
        self.timeout = timeout

    def _headers(self) -> dict:
        return {"x-goog-api-key": self.api_key, "Api-Revision": API_REVISION, "Content-Type": "application/json"}

    def request(self, method: str, path: str, *, json: dict | None = None, timeout: float | None = None) -> dict:
        try:
            r = httpx.request(method, f"{BASE_URL}/{path.lstrip('/')}", headers=self._headers(), json=json,
                              timeout=timeout or self.timeout)
        except httpx.TimeoutException:
            raise GeminiError("Gemini: hết thời gian chờ", code="TIMEOUT", retryable=True)
        except httpx.HTTPError as e:
            raise GeminiError(f"Gemini: không kết nối được ({e})", code="PROVIDER_UNAVAILABLE", retryable=True)
        if r.status_code >= 400:
            raise _http_error(r)
        return r.json() if r.content else {}

    def create_interaction(self, body: dict, timeout: float | None = None) -> dict:
        return self.request("POST", "interactions", json=body, timeout=timeout)

    def get_interaction(self, interaction_id: str) -> dict:
        return self.request("GET", f"interactions/{interaction_id}")

    def cancel_interaction(self, interaction_id: str) -> dict:
        return self.request("POST", f"interactions/{interaction_id}/cancel")

    def get_file(self, file_name: str) -> dict:
        return self.request("GET", file_name if file_name.startswith("files/") else f"files/{file_name}")

    def download(self, url: str, dest: str, max_redirects: int = 5) -> str:
        """Tải file về `dest`. Chỉ gửi key tới host của Gemini API; chuyển hướng sang host khác thì không kèm key."""
        if url.startswith("files/"):
            url = f"{BASE_URL}/{url}:download?alt=media"
        for _ in range(max_redirects + 1):
            p = urlparse(url)
            if p.scheme != "https":
                raise GeminiError("Gemini: URL tải về phải là https", code="BAD_RESPONSE", retryable=False)
            headers = {"x-goog-api-key": self.api_key} if p.hostname == API_HOST else {}
            try:
                with httpx.stream("GET", url, headers=headers, timeout=self.timeout * 5, follow_redirects=False) as r:
                    if r.status_code in (301, 302, 303, 307, 308):
                        url = urljoin(url, r.headers.get("location", ""))
                        continue
                    if r.status_code >= 400:
                        r.read()
                        raise _http_error(r)
                    with open(dest, "wb") as f:
                        for chunk in r.iter_bytes():
                            f.write(chunk)
                    return dest
            except httpx.TimeoutException:
                raise GeminiError("Gemini: tải file quá thời gian", code="TIMEOUT", retryable=True)
            except httpx.HTTPError as e:
                raise GeminiError(f"Gemini: lỗi tải file ({e})", code="DOWNLOAD_FAILED", retryable=True)
        raise GeminiError("Gemini: chuyển hướng quá nhiều lần", code="DOWNLOAD_FAILED", retryable=False)


def _http_error(r: httpx.Response) -> GeminiError:
    try:
        msg = (r.json().get("error") or {}).get("message") or r.text
    except Exception:  # noqa: BLE001
        msg = r.text
    msg = str(msg)[:400]
    s = r.status_code
    if s in (401, 403):
        return GeminiError(f"Gemini từ chối quyền ({s}): {msg}", code="AUTH_FAILED", retryable=False, status=s)
    if s == 429:
        return GeminiError(f"Gemini: vượt hạn mức gọi API: {msg}", code="RATE_LIMITED", retryable=True, status=s)
    if s >= 500:
        return GeminiError(f"Gemini lỗi máy chủ {s}: {msg}", code="PROVIDER_ERROR", retryable=True, status=s)
    return GeminiError(f"Gemini lỗi {s}: {msg}", code="BAD_REQUEST", retryable=False, status=s)


def find_output(data, kind: str) -> dict | None:
    """Tìm phần tử đầu ra cuối cùng có type == kind ("video" | "audio") trong steps[].content[] của model_output."""
    found = None
    for step in (data or {}).get("steps") or []:
        if step.get("type") != "model_output":
            continue
        for item in step.get("content") or []:
            if isinstance(item, dict) and item.get("type") == kind:
                found = item
    return found


def decode_to_file(item: dict, dest: str) -> str:
    with open(dest, "wb") as f:
        f.write(base64.b64decode(item["data"]))
    return dest
