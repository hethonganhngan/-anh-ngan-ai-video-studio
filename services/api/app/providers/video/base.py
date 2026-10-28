"""VideoProvider interface — mọi nhà cung cấp video đi qua 6 phương thức chuẩn."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class GenerationSpec:
    job_ref: str
    prompt_text: str
    negative_prompt: str = ""
    duration_sec: int = 8
    width: int = 1080
    height: int = 1920
    aspect_ratio: str = "9:16"
    scene_title: str = ""
    dialogue: list = field(default_factory=list)
    attempt_no: int = 1
    reference_image_paths: list = field(default_factory=list)
    seed: int | None = None


@dataclass
class ProviderStatus:
    state: str  # SUBMITTED | RUNNING | SUCCEEDED | FAILED | CANCELLED | NEEDS_MANUAL_ACTION
    progress: int = 0
    error_code: str | None = None
    error_message: str | None = None


class ProviderError(Exception):
    def __init__(self, message: str, code: str = "PROVIDER_ERROR", retryable: bool = True):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class VideoProvider(ABC):
    code = "abstract"
    name = "Abstract"
    kind = "MOCK"  # MOCK | MANUAL | REAL_API
    is_real = False
    unit_cost_vnd_per_sec = Decimal(0)
    max_duration_sec = 8
    supported_aspects = ("9:16",)

    def validate_capabilities(self, spec: GenerationSpec) -> list[str]:
        issues = []
        if spec.aspect_ratio not in self.supported_aspects:
            issues.append(f"{self.name} không hỗ trợ tỉ lệ {spec.aspect_ratio}")
        if spec.duration_sec > self.max_duration_sec:
            issues.append(f"{self.name} chỉ hỗ trợ tối đa {self.max_duration_sec}s/cảnh")
        if not spec.prompt_text.strip():
            issues.append("Prompt rỗng")
        return issues

    def estimate_cost(self, spec: GenerationSpec) -> Decimal:
        return (Decimal(self.unit_cost_vnd_per_sec) * spec.duration_sec).quantize(Decimal("0.01"))

    @abstractmethod
    def submit_generation(self, spec: GenerationSpec) -> str: ...

    @abstractmethod
    def get_status(self, provider_job_id: str) -> ProviderStatus: ...

    @abstractmethod
    def get_result(self, provider_job_id: str) -> str:
        """Trả về đường dẫn file MP4 cục bộ đã tải về."""

    @abstractmethod
    def cancel_job(self, provider_job_id: str) -> bool: ...

    def info(self) -> dict:
        return {"code": self.code, "name": self.name, "kind": self.kind, "is_real": self.is_real,
                "unit_cost_vnd_per_sec": float(self.unit_cost_vnd_per_sec), "max_duration_sec": self.max_duration_sec,
                "supported_aspects": list(self.supported_aspects)}
