"""Claude (Anthropic API) — kết nối THẬT, chỉ dùng ở PRODUCTION khi có API key hợp lệ.

Trạng thái: adapter đã viết theo SDK chính thức `anthropic`; CHƯA được xác minh bằng key thật trong repo này.
"""
import json
import time

from app.core.config import get_settings
from app.providers.llm.base import LLMError, LLMProvider, LLMResult

# USD / 1M token (bảng giá công bố, cập nhật khi Anthropic thay đổi)
PRICING_USD_PER_MTOK = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}


class AnthropicProvider(LLMProvider):
    code = "anthropic"
    is_real = True

    def __init__(self, api_key: str, model: str | None = None, timeout: float = 120.0):
        import anthropic

        self._anthropic = anthropic
        self.model = model or get_settings().anthropic_model
        self.client = anthropic.Anthropic(api_key=api_key, timeout=timeout, max_retries=2)

    def estimate_cost_vnd(self, input_tokens, output_tokens):
        pin, pout = PRICING_USD_PER_MTOK.get(self.model, PRICING_USD_PER_MTOK["claude-opus-5-5"])
        usd = input_tokens / 1e6 * pin + output_tokens / 1e6 * pout
        return round(usd * get_settings().usd_vnd_rate, 2)

    def complete_json(self, *, system, prompt, schema, max_tokens=16000, mock_fn=None):
        a = self._anthropic
        start = time.perf_counter()
        try:
            resp = self.client.beta.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                output_config={"effort": "medium", "format": {"type": "json_schema", "schema": schema}},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except a.RateLimitError as e:
            raise LLMError(f"Claude rate limit: {e}", code="RATE_LIMITED", retryable=True)
        except a.APITimeoutError as e:
            raise LLMError(f"Claude timeout: {e}", code="TIMEOUT", retryable=True)
        except a.AuthenticationError:
            raise LLMError("API key Anthropic không hợp lệ", code="AUTH_FAILED")
        except a.APIStatusError as e:
            raise LLMError(f"Claude lỗi {e.status_code}: {e.message}", code="PROVIDER_ERROR", retryable=e.status_code >= 500)
        except a.APIConnectionError as e:
            raise LLMError(f"Không kết nối được Anthropic: {e}", code="PROVIDER_UNAVAILABLE", retryable=True)
        if resp.stop_reason == "refusal":
            cat = getattr(resp.stop_details, "category", None) if resp.stop_details else None
            raise LLMError(f"Claude từ chối yêu cầu (category={cat})", code="REFUSAL")
        if resp.stop_reason == "max_tokens":
            raise LLMError("Kết quả bị cắt do max_tokens", code="TRUNCATED", retryable=True)
        text = "".join(b.text for b in resp.content if b.type == "text")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            raise LLMError("Claude trả về JSON không hợp lệ", code="INVALID_JSON", retryable=True)
        tin, tout = resp.usage.input_tokens, resp.usage.output_tokens
        return LLMResult(data=data, model=resp.model, provider=self.code, input_tokens=tin, output_tokens=tout,
                         cost_vnd=self.estimate_cost_vnd(tin, tout), simulated=False, raw_text=text,
                         meta={"latency_ms": int((time.perf_counter() - start) * 1000), "request_id": resp._request_id})
