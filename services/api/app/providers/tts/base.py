"""TTS Provider interface — tạo giọng đọc (voice-over) từ văn bản."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class TTSRequest:
    text: str
    voice_id: str = ""
    style: str = ""  # mô tả giọng: vùng miền, sắc thái, tốc độ


@dataclass
class TTSResult:
    path: str  # file WAV cục bộ
    duration_sec: float
    simulated: bool = True
    meta: dict = field(default_factory=dict)


class TTSError(Exception):
    def __init__(self, message: str, code: str = "TTS_ERROR", retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class TTSProvider(ABC):
    code = "abstract"
    name = "Abstract"
    is_real = False
    unit_cost_vnd_per_sec = 0.0

    @abstractmethod
    def synthesize(self, req: TTSRequest) -> TTSResult: ...

    def estimate_seconds(self, text: str) -> float:
        return max(1.0, len(text) / 14.0)  # ~14 ký tự/giây tiếng Việt đọc vừa phải

    def estimate_cost_vnd(self, text: str) -> float:
        return round(self.estimate_seconds(text) * float(self.unit_cost_vnd_per_sec), 2)
