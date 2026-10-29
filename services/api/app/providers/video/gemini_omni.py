"""Gemini Omni Flash (Gemini API) — tạo video AI bằng API chính thức của Google.

Veo 3.1 Preview trên Gemini API đã ngừng 22/10/2026; Google thay bằng `gemini-omni-1.1-flash` (Interactions API).
- Ưu tiên chạy nền (`background: true`) → provider_job_id = "int:<interaction id>", poll GET interactions/{id}.
- Nếu API không nhận chạy nền: gọi đồng bộ với delivery=uri → provider_job_id = "file:<files/...>", poll Files API.
Thoại tiếng Việt do TTS đảm nhận (mặc định video chỉ có âm thanh môi trường) vì Omni chỉ cam kết tiếng Anh.
Chỉ đánh dấu VERIFIED sau khi M15 → Test gọi API thật thành công.
"""
import base64
import mimetypes
import tempfile
from decimal import Decimal

from app.providers.google_genai import GeminiClient, GeminiError, decode_to_file, find_output
from app.providers.video.base import GenerationSpec, ProviderError, ProviderStatus, VideoProvider

DEFAULT_MODEL = "gemini-omni-1.1-flash"
NO_SPEECH = ("Không có lời thoại, không có người nói, không có chữ trên màn hình; chỉ âm thanh môi trường. "
             "No spoken dialogue, no narration, no on-screen text; ambient sound only.")


def interaction_error(data: dict) -> tuple[str | None, str | None]:
    """Lỗi của interaction: mảng `errors` [{code, message}] (hoặc `error` đơn lẻ)."""
    errs = data.get("errors") or ([data["error"]] if data.get("error") else [])
    for e in errs:
        if isinstance(e, dict):
            return e.get("code"), e.get("message")
        return None, str(e)
    return None, None


def _err(e: GeminiError) -> ProviderError:
    return ProviderError(str(e), code=e.code, retryable=e.retryable)


class GeminiOmniProvider(VideoProvider):
    kind = "REAL_API"
    is_real = True
    supported_aspects = ("9:16", "16:9")

    def __init__(self, code: str, name: str, api_key: str | None, config: dict, unit_cost_vnd_per_sec=0,
                 timeout: float = 60.0):
        self.code = code
        self.name = name
        self.config = config or {}
        self.api_key = api_key
        self.timeout = timeout
        self.model = self.config.get("model", DEFAULT_MODEL)
        self.resolution = self.config.get("resolution", "720p")
        self.speech_in_video = bool(self.config.get("speech_in_video", False))
        self.max_duration_sec = int(self.config.get("max_duration_sec", 10))
        self.unit_cost_vnd_per_sec = Decimal(str(unit_cost_vnd_per_sec or self.config.get("unit_cost_vnd_per_sec", 0)))

    def _client(self) -> GeminiClient:
        try:
            return GeminiClient(self.api_key, timeout=self.timeout)
        except GeminiError as e:
            raise _err(e)

    def build_prompt(self, spec: GenerationSpec) -> str:
        parts = [spec.prompt_text.strip(), f"Thời lượng mong muốn: khoảng {spec.duration_sec} giây."]
        if spec.negative_prompt:
            parts.append(f"Tránh: {spec.negative_prompt.strip()}")  # Omni không có tham số negative prompt
        if not self.speech_in_video:
            parts.append(NO_SPEECH)
        return "\n\n".join(p for p in parts if p)

    def build_body(self, spec: GenerationSpec, background: bool) -> dict:
        prompt = self.build_prompt(spec)
        if spec.reference_image_paths:
            items = [{"type": "text", "text": prompt}]
            for path in spec.reference_image_paths[:3]:
                with open(path, "rb") as f:
                    items.append({"type": "image", "mime_type": mimetypes.guess_type(path)[0] or "image/png",
                                  "data": base64.b64encode(f.read()).decode()})
            inp = items
        else:
            inp = prompt
        fmt = {"type": "video", "aspect_ratio": spec.aspect_ratio, "resolution": self.resolution}
        body = {"model": self.model, "input": inp, "response_format": fmt}
        if background:
            body["background"] = True
        else:
            fmt["delivery"] = "uri"
        return body

    def submit_generation(self, spec: GenerationSpec) -> str:
        c = self._client()
        if self.config.get("background", True):
            try:
                data = c.create_interaction(self.build_body(spec, background=True))
                if data.get("status") in ("in_progress", "completed") and data.get("id"):
                    return f"int:{data['id']}"
            except GeminiError as e:
                if not (e.status == 400 and "background" in str(e).lower()):
                    raise _err(e)
        # Đồng bộ: yêu cầu chạy tới khi có video (worker giữ khoá job nên không bị gửi trùng)
        try:
            data = c.create_interaction(self.build_body(spec, background=False), timeout=900)
        except GeminiError as e:
            raise _err(e)
        item = find_output(data, "video")
        if not item:
            raise ProviderError(f"{self.name}: phản hồi không có video ({data.get('status')})", code="BAD_RESPONSE",
                                retryable=False)
        if item.get("uri"):
            return "file:" + item["uri"].split("/v1beta/")[-1].split(":")[0]
        fd, path = tempfile.mkstemp(suffix=".mp4")
        with open(fd, "wb"):
            pass
        decode_to_file(item, path)
        return f"local:{path}"

    def get_status(self, provider_job_id: str) -> ProviderStatus:
        kind, _, ref = provider_job_id.partition(":")
        if kind == "local":
            return ProviderStatus(state="SUCCEEDED", progress=100)
        c = self._client()
        try:
            if kind == "file":
                st = (c.get_file(ref).get("state") or "").upper()
                if st == "ACTIVE":
                    return ProviderStatus(state="SUCCEEDED", progress=100)
                if st == "FAILED":
                    return ProviderStatus(state="FAILED", error_code="PROVIDER_FAILED", error_message="Gemini xử lý file lỗi")
                return ProviderStatus(state="RUNNING", progress=80)
            data = c.get_interaction(ref)
        except GeminiError as e:
            raise _err(e)
        st = data.get("status")
        if st == "completed":
            return ProviderStatus(state="SUCCEEDED", progress=100)
        if st in ("failed", "cancelled"):
            code, msg = interaction_error(data)
            if code == "RESOURCE_EXHAUSTED":  # hết hạn mức / chưa bật Billing — thử lại vô ích
                return ProviderStatus(state="NEEDS_MANUAL_ACTION", error_code="QUOTA_EXHAUSTED",
                                      error_message="Gemini hết hạn mức (RESOURCE_EXHAUSTED): bật Billing cho Google Cloud project "
                                                    "của key (video không có gói miễn phí) hoặc chờ hạn mức phục hồi, rồi tạo lại cảnh.")
            return ProviderStatus(state="FAILED" if st == "failed" else "CANCELLED", error_code=code or "PROVIDER_FAILED",
                                  error_message=(msg or f"Gemini báo {st}")[:500])
        if st == "requires_action":
            return ProviderStatus(state="NEEDS_MANUAL_ACTION", error_message="Gemini yêu cầu thao tác bổ sung")
        return ProviderStatus(state="RUNNING", progress=50)

    def get_result(self, provider_job_id: str) -> str:
        kind, _, ref = provider_job_id.partition(":")
        if kind == "local":
            return ref
        c = self._client()
        fd, path = tempfile.mkstemp(suffix=".mp4")
        with open(fd, "wb"):
            pass
        try:
            if kind == "file":
                return c.download(ref, path)
            item = find_output(c.get_interaction(ref), "video")
            if not item:
                raise ProviderError(f"{self.name}: chưa có video", code="NOT_READY", retryable=True)
            if item.get("data"):
                return decode_to_file(item, path)
            return c.download(item["uri"], path)
        except GeminiError as e:
            raise _err(e)

    def cancel_job(self, provider_job_id: str) -> bool:
        kind, _, ref = provider_job_id.partition(":")
        if kind != "int":
            return False
        try:
            self._client().cancel_interaction(ref)
            return True
        except (GeminiError, ProviderError):
            return False

    def test_connection(self) -> str:
        """Kiểm tra key mà không tạo video (không tốn phí): đọc thông tin model."""
        try:
            info = self._client().request("GET", f"models/{self.model}")
        except GeminiError as e:
            raise _err(e)
        return info.get("displayName") or info.get("name") or self.model
