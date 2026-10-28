"""LLM Provider interface. Agent dùng chung hạ tầng mô hình qua interface này."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class LLMResult:
    data: dict
    model: str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_vnd: float = 0.0
    simulated: bool = True
    raw_text: str = ""
    meta: dict = field(default_factory=dict)


class LLMProvider(ABC):
    code = "abstract"
    is_real = False

    @abstractmethod
    def complete_json(self, *, system: str, prompt: str, schema: dict, max_tokens: int = 16000,
                      mock_fn=None) -> LLMResult:
        """Sinh JSON theo schema. mock_fn: hàm tạo kết quả xác định cho Mock provider."""

    def estimate_cost_vnd(self, input_tokens: int, output_tokens: int) -> float:
        return 0.0


class LLMError(Exception):
    def __init__(self, message: str, code: str = "LLM_ERROR", retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable
