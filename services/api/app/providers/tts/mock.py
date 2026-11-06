"""MockTTSProvider — DEMO: tạo file WAV thật (tiếng bíp) dài theo độ dài văn bản. KHÔNG phải giọng AI."""
import hashlib
import subprocess
import tempfile

from app.core.config import get_settings
from app.providers.tts.base import TTSProvider, TTSRequest, TTSResult, VoiceOption


class MockTTSProvider(TTSProvider):
    code = "mock_tts"
    name = "Mock TTS (DEMO)"
    unit_cost_vnd_per_sec = 10.0

    def voice_options(self) -> list[VoiceOption]:
        return [VoiceOption("mock-nu-1", "female", "Nam"), VoiceOption("mock-nam-1", "male", "Nam"),
                VoiceOption("mock-nu-2", "female", "Bắc"), VoiceOption("mock-nam-2", "male", "Bắc")]

    def synthesize(self, req: TTSRequest) -> TTSResult:
        dur = round(self.estimate_seconds(req.text), 2)
        freq = 300 + int(hashlib.md5(req.text.encode()).hexdigest()[:2], 16)
        fd, path = tempfile.mkstemp(suffix=".wav")
        with open(fd, "wb"):
            pass
        subprocess.run([get_settings().ffmpeg_bin, "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                        f"sine=frequency={freq}:duration={dur}", "-af", "volume=0.25", "-ar", "24000", "-ac", "1", path],
                       check=True, timeout=60)
        return TTSResult(path=path, duration_sec=dur, simulated=True, meta={"voice": req.voice_id or "mock"})
