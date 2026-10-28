"""Mock LLM: không gọi API, kết quả xác định từ mock_fn của Agent. Token & chi phí là MÔ PHỎNG."""
import json

from app.providers.llm.base import LLMError, LLMProvider, LLMResult


class MockLLMProvider(LLMProvider):
    code = "mock-llm"
    is_real = False
    model = "mock-deterministic-v1"
    # Đơn giá mô phỏng để kiểm thử ngân sách (VND / 1K token)
    sim_vnd_per_1k_in = 0.0
    sim_vnd_per_1k_out = 0.0

    def complete_json(self, *, system, prompt, schema, max_tokens=4000, mock_fn=None):
        if mock_fn is None:
            raise LLMError("Mock provider cần mock_fn", code="MOCK_NOT_IMPLEMENTED")
        if "[[MOCK_LLM_TIMEOUT]]" in prompt:
            raise LLMError("Mock: hết thời gian chờ LLM", code="TIMEOUT", retryable=True)
        data = mock_fn()
        text = json.dumps(data, ensure_ascii=False)
        tin = max(1, (len(system) + len(prompt)) // 4)
        tout = max(1, len(text) // 4)
        return LLMResult(data=data, model=self.model, provider=self.code, input_tokens=tin, output_tokens=tout,
                         cost_vnd=self.estimate_cost_vnd(tin, tout), simulated=True, raw_text=text)

    def estimate_cost_vnd(self, input_tokens, output_tokens):
        return round(input_tokens / 1000 * self.sim_vnd_per_1k_in + output_tokens / 1000 * self.sim_vnd_per_1k_out, 2)
