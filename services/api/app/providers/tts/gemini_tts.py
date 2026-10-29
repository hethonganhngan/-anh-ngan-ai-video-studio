"""Gemini TTS (Gemini API) — giọng đọc AI tiếng Việt, kết nối THẬT.

Tài liệu: https://ai.google.dev/gemini-api/docs/speech-generation (Interactions API, tự nhận diện tiếng Việt).
Đầu ra WAV 24 kHz mono 16-bit. 30 giọng dựng sẵn (Kore, Puck, Charon, Aoede, Leda...).
"""
import tempfile
import wave

from app.providers.google_genai import GeminiClient, GeminiError, decode_to_file, find_output
from app.providers.tts.base import TTSError, TTSProvider, TTSRequest, TTSResult

DEFAULT_MODEL = "gemini-3.8-flash-tts"
DEFAULT_VOICE = "Kore"
VOICES = ["Zephyr", "Puck", "Charon", "Kore", "Fenrir", "Leda", "Orus", "Aoede", "Callirrhoe", "Autonoe", "Enceladus",
          "Iapetus", "Umbriel", "Algieba", "Despina", "Erinome", "Algenib", "Rasalgethi", "Laomedeia", "Achernar",
          "Alnilam", "Schedar", "Gacrux", "Pulcherrima", "Achird", "Zubenelgenubi", "Vindemiatrix", "Sadachbia",
          "Sadaltager", "Sulafat"]


class GeminiTTSProvider(TTSProvider):
    code = "gemini_tts"
    name = "Gemini TTS"
    is_real = True

    def __init__(self, api_key: str | None, config: dict | None = None, unit_cost_vnd_per_sec=12):
        self.api_key = api_key
        self.config = config or {}
        self.model = self.config.get("model", DEFAULT_MODEL)
        self.unit_cost_vnd_per_sec = float(unit_cost_vnd_per_sec or 0)

    def _client(self) -> GeminiClient:
        try:
            return GeminiClient(self.api_key, timeout=120)
        except GeminiError as e:
            raise TTSError(str(e), code=e.code)

    def synthesize(self, req: TTSRequest) -> TTSResult:
        voice = req.voice_id if req.voice_id in VOICES else self.config.get("default_voice", DEFAULT_VOICE)
        text = f"{req.style.strip()}: {req.text}" if req.style.strip() and self.config.get("style_prompt", True) else req.text
        body = {"model": self.model,
                "input": [{"type": "user_input", "content": [{"type": "text", "text": text}]}],
                "response_format": {"type": "audio", "mime_type": "audio/wav", "sample_rate": 24000},
                "generation_config": {"speech_config": [{"voice": voice}]}}
        try:
            data = self._client().create_interaction(body)
        except GeminiError as e:
            raise TTSError(str(e), code=e.code, retryable=e.retryable)
        item = find_output(data, "audio")
        if not item or not item.get("data"):
            raise TTSError(f"Gemini TTS không trả về âm thanh ({data.get('status')})", code="BAD_RESPONSE")
        fd, path = tempfile.mkstemp(suffix=".wav")
        with open(fd, "wb"):
            pass
        decode_to_file(item, path)
        if not open(path, "rb").read(4) == b"RIFF":  # PCM thô (audio/l16) → bọc header WAV
            raw = open(path, "rb").read()
            with wave.open(path, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(24000)
                w.writeframes(raw)
        with wave.open(path, "rb") as w:
            dur = w.getnframes() / float(w.getframerate())
        return TTSResult(path=path, duration_sec=round(dur, 2), simulated=False,
                         meta={"voice": voice, "model": self.model, "interaction_id": data.get("id")})

    def test_connection(self) -> str:
        try:
            info = self._client().request("GET", f"models/{self.model}")
        except GeminiError as e:
            raise TTSError(str(e), code=e.code)
        return info.get("displayName") or self.model
