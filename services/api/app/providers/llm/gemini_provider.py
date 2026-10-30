"""Gemini (Gemini API, Interactions API) — LLM THẬT cho A02/A08/A09, dùng chung key Gemini với video và TTS.

Tài liệu: https://ai.google.dev/gemini-api/docs/structured-output · https://ai.google.dev/api/interactions-api
JSON theo schema qua response_format {type: text, mime_type: application/json, schema}.
"""
import json
import time

from app.core.config import get_settings
from app.providers.google_genai import GeminiClient, GeminiError
from app.providers.llm.base import LLMError, LLMProvider, LLMResult

DEFAULT_MODEL = "gemini-3.8-flash"
# USD / 1M token (vào, ra gồm thinking) — dùng mức giá SAU đợt tăng (12/2026–01/2027) để ước tính an toàn
PRICING_USD_PER_MTOK = {
    "gemini-4-argon": (4.00, 20.00),
    "gemini-3.8-flash": (1.50, 7.50),
    "gemini-3.5-flash-lite": (0.30, 2.50),
}
MODELS = list(PRICING_USD_PER_MTOK)


def _err(e: GeminiError) -> LLMError:
    code = {"AUTH_FAILED": "AUTH_FAILED", "RATE_LIMITED": "RATE_LIMITED", "TIMEOUT": "TIMEOUT",
            "PROVIDER_UNAVAILABLE": "PROVIDER_UNAVAILABLE", "NOT_CONFIGURED": "AUTH_FAILED"}.get(e.code, "PROVIDER_ERROR")
    return LLMError(str(e), code=code, retryable=e.retryable)


class GeminiLLMProvider(LLMProvider):
    code = "gemini"
    is_real = True

    def __init__(self, api_key: str, model: str | None = None, config: dict | None = None, timeout: float = 600.0):
        self.config = config or {}
        self.model = model or self.config.get("model", DEFAULT_MODEL)
        self.thinking_level = self.config.get("thinking_level", "medium")
        try:
            self.client = GeminiClient(api_key, timeout=timeout)
        except GeminiError as e:
            raise _err(e)

    def estimate_cost_vnd(self, input_tokens, output_tokens):
        pin, pout = PRICING_USD_PER_MTOK.get(self.model, PRICING_USD_PER_MTOK["gemini-4-argon"])
        usd = input_tokens / 1e6 * pin + output_tokens / 1e6 * pout
        return round(usd * get_settings().usd_vnd_rate, 2)

    def _body(self, system: str, prompt: str, schema: dict, max_tokens: int, inline_system: bool) -> dict:
        body = {"model": self.model,
                "input": f"{system}\n\n---\n\n{prompt}" if inline_system else prompt,
                "response_format": {"type": "text", "mime_type": "application/json", "schema": schema},
                "generation_config": {"max_output_tokens": max_tokens, "thinking_level": self.thinking_level}}
        if not inline_system:
            body["system_instruction"] = system
        return body

    def complete_json(self, *, system, prompt, schema, max_tokens=16000, mock_fn=None):
        start = time.perf_counter()
        try:
            try:
                data = self.client.create_interaction(self._body(system, prompt, schema, max_tokens, inline_system=False))
            except GeminiError as e:
                if not (e.status == 400 and "system_instruction" in str(e)):
                    raise
                data = self.client.create_interaction(self._body(system, prompt, schema, max_tokens, inline_system=True))
        except GeminiError as e:
            raise _err(e)
        status = data.get("status")
        if status in ("failed", "cancelled"):
            from app.providers.video.gemini_omni import interaction_error

            code, msg = interaction_error(data)
            if code == "RESOURCE_EXHAUSTED":
                raise LLMError("Gemini hết hạn mức (RESOURCE_EXHAUSTED) — kiểm tra Billing/hạn mức của key", code="RATE_LIMITED")
            raise LLMError(f"Gemini báo {status}: {code or ''} {msg or ''}".strip(), code="PROVIDER_ERROR", retryable=status == "failed")
        text = "".join(item.get("text", "") for step in data.get("steps") or [] if step.get("type") == "model_output"
                       for item in step.get("content") or [] if isinstance(item, dict) and item.get("type") == "text")
        if not text.strip():
            raise LLMError("Gemini không trả về nội dung (có thể bị bộ lọc an toàn chặn)", code="REFUSAL")
        try:
            out = json.loads(text)
        except json.JSONDecodeError:
            raise LLMError("Gemini trả về JSON không hợp lệ", code="INVALID_JSON", retryable=True)
        u = data.get("usage") or data
        tin = int(u.get("total_input_tokens") or 0)
        tout = int(u.get("total_output_tokens") or 0) + int(u.get("total_thought_tokens") or 0)
        return LLMResult(data=out, model=data.get("model") or self.model, provider=self.code, input_tokens=tin,
                         output_tokens=tout, cost_vnd=self.estimate_cost_vnd(tin, tout), simulated=False, raw_text=text,
                         meta={"latency_ms": int((time.perf_counter() - start) * 1000), "interaction_id": data.get("id")})

    def test_connection(self) -> str:
        try:
            info = self.client.request("GET", f"models/{self.model}")
        except GeminiError as e:
            raise _err(e)
        return info.get("displayName") or self.model
