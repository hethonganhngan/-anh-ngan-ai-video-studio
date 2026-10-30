"""VieNeu-TTS chạy trên máy (D23) — đọc lời thoại bằng GIỌNG NHÂN BẢN từ bản ghi âm chính chủ của Voice Profile.

Máy chủ: scripts/windows/start-vieneu.ps1 → API tương thích OpenAI ở 127.0.0.1:8200 (chỉ nhận localhost, không phí).
- Giọng = tên Voice Profile (vd. VOI-2610-0004). Máy chủ chỉ giữ giọng trong bộ nhớ → báo "unknown voice" thì tự nạp
  lại từ bản ghi âm tham chiếu (đã khoá trong Voice Lock): cắt khoảng lặng đầu, lấy 8 giây đầu có tiếng → POST /v1/voices.
- Kết quả PCM 16-bit mono → bọc thành WAV. Bản ghi âm gốc không bị sửa; đoạn 8 giây chỉ là file tạm.
"""
import os
import re
import subprocess
import tempfile
import wave

import httpx
from app.core.config import get_settings
from app.providers.tts.base import TTSError, TTSProvider, TTSRequest, TTSResult, VoiceOption

DEFAULT_URL = "http://127.0.0.1:8200"
SAMPLE_RATE = 24000
REF_SECONDS = 8  # VieNeu nhận đoạn mẫu 3–8 giây


class VieNeuLocalProvider(TTSProvider):
    code = "vieneu_local"
    name = "VieNeu-TTS (máy cục bộ, giọng nhân bản)"
    is_real = True

    def __init__(self, config: dict | None = None, timeout: float = 300.0):
        self.config = config or {}
        self.base_url = self.config.get("base_url", DEFAULT_URL).rstrip("/")
        self.timeout = timeout
        self.unit_cost_vnd_per_sec = 0.0  # chạy trên máy — không tính phí
        # VieNeu bỏ qua tham số tốc độ → tăng/giảm nhịp đọc sau khi đọc bằng atempo (giữ cao độ giọng)
        self.speed = min(1.5, max(0.75, float(self.config.get("speed", 1.0))))

    def _url(self, path: str) -> str:
        if not re.match(r"^http://(127\.0\.0\.1|localhost):\d+$", self.base_url):
            raise TTSError("VieNeu chỉ được gọi trên máy này (127.0.0.1)", code="BAD_URL")
        return self.base_url + path

    def _post(self, path: str, **kw) -> httpx.Response:
        try:
            return httpx.post(self._url(path), timeout=self.timeout, **kw)
        except httpx.HTTPError as e:
            raise TTSError(f"Không kết nối được VieNeu ({self.base_url}) — chạy scripts/windows/start-vieneu.ps1. {e}",
                           code="PROVIDER_UNAVAILABLE", retryable=True)

    def _reference_clip(self, path: str) -> str:
        """Bỏ khoảng lặng đầu, lấy REF_SECONDS giây đầu có tiếng, WAV mono 24 kHz."""
        fd, out = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        cmd = [get_settings().ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error", "-i", path,
               "-af", "silenceremove=start_periods=1:start_threshold=-40dB:start_silence=0.2",
               "-t", str(REF_SECONDS), "-ac", "1", "-ar", str(SAMPLE_RATE), out]
        try:
            subprocess.run(cmd, check=True, timeout=120)
        except (subprocess.SubprocessError, OSError) as e:
            raise TTSError(f"Không cắt được bản ghi âm tham chiếu: {e}", code="BAD_REFERENCE")
        return out

    def enroll(self, voice: str, reference_path: str) -> None:
        clip = self._reference_clip(reference_path)
        try:
            with open(clip, "rb") as f:
                r = self._post("/v1/voices", data={"name": voice, "denoise": "true", "description": "Anh Ngan"},
                               files={"file": ("reference.wav", f, "audio/wav")})
        finally:
            os.unlink(clip)
        if r.status_code >= 400:
            raise TTSError(f"VieNeu không nhận giọng mẫu: {r.text[:300]}", code="ENROLL_FAILED")

    def _speech(self, text: str, voice: str) -> httpx.Response:
        return self._post("/v1/audio/speech", json={"model": "vieneu-v3-turbo", "input": text, "voice": voice,
                                                    "response_format": "pcm", "sample_rate": SAMPLE_RATE})

    def synthesize(self, req: TTSRequest) -> TTSResult:
        voice = req.voice_id
        if not voice:
            raise TTSError("Voice Profile chưa có tên giọng VieNeu", code="VOICE_NOT_SET")
        r = self._speech(req.text, voice)
        if r.status_code == 400 and "unknown voice" in r.text:
            if not req.reference_audio_path or not os.path.exists(req.reference_audio_path):
                raise TTSError("Voice Profile chưa có bản ghi âm tham chiếu để nhân bản giọng", code="NO_REFERENCE")
            self.enroll(voice, req.reference_audio_path)
            r = self._speech(req.text, voice)
        if r.status_code == 429:
            raise TTSError("VieNeu đang bận — thử lại sau", code="BUSY", retryable=True)
        if r.status_code >= 400 or not r.content:
            raise TTSError(f"VieNeu lỗi {r.status_code}: {r.text[:300]}", code="PROVIDER_ERROR")
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SAMPLE_RATE)
            w.writeframes(r.content)
        dur = len(r.content) / 2 / SAMPLE_RATE
        if self.speed != 1.0:
            path, dur = self._tempo(path), dur / self.speed
        return TTSResult(path=path, duration_sec=round(dur, 2), simulated=False,
                         meta={"voice": voice, "engine": "vieneu", "speed": self.speed})

    def _tempo(self, path: str) -> str:
        fd, out = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        cmd = [get_settings().ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error", "-i", path,
               "-af", f"atempo={self.speed}", out]
        try:
            subprocess.run(cmd, check=True, timeout=120)
        except (subprocess.SubprocessError, OSError) as e:
            raise TTSError(f"Không chỉnh được tốc độ đọc: {e}", code="TEMPO_FAILED")
        finally:
            os.unlink(path)
        return out

    def voice_options(self) -> list[VoiceOption]:
        """Giọng dựng sẵn của VieNeu (mô tả dạng "Nữ · Nam · …"); bỏ giọng nhân bản (không có giới tính)."""
        try:
            data = httpx.get(self._url("/v1/voices"), timeout=10).json().get("data") or []
        except (httpx.HTTPError, ValueError, TTSError):
            return []
        out = []
        for v in data:
            if v.get("gender") not in ("female", "male"):
                continue
            bits = [b.strip() for b in (v.get("description") or "").split("·")]
            out.append(VoiceOption(v["id"], v["gender"], bits[1] if len(bits) > 1 else ""))
        return out

    def test_connection(self) -> str:
        try:
            info = httpx.get(self._url("/health"), timeout=10).json()
        except (httpx.HTTPError, ValueError) as e:
            raise TTSError(f"Không kết nối được VieNeu ({self.base_url}) — chạy scripts/windows/start-vieneu.ps1. {e}",
                           code="PROVIDER_UNAVAILABLE")
        return f"VieNeu sẵn sàng · {info.get('backend', '?')}"
