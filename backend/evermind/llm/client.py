"""Owner: A. OpenAI-compatible gateway (architecture.md §LLM gateway).

Provider is env config only (`AI_BASE_URL`/`AI_MODEL`/`AI_API_KEY`), never an
import. No prompts live here — callers (`ingestion`, `knowledge`) own prompts;
this module only does the call, retry, and schema validation.
"""
from __future__ import annotations

import json
import logging
import re
import time

from pydantic import BaseModel, ValidationError

from evermind.config import settings

logger = logging.getLogger(__name__)

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


class LLMUnavailable(RuntimeError):
    """No key configured, provider unreachable, or output never validated —
    callers degrade gracefully (structured-only answers), never half-persist."""


class LLMCallResult(BaseModel):
    window_id: int | None = None
    model: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    validation_attempts: int


def _extract_json(text: str) -> str:
    """Models love to wrap JSON in prose/fences — take the fenced block if any,
    else the outermost {...} span, else the raw text (validation will judge)."""
    match = _FENCE.search(text)
    if match:
        return match.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return text[start:end + 1]
    return text


class LLMGateway:
    def __init__(self, *, base_url: str | None = None, model: str | None = None,
                 api_key: str | None = None, timeout: float = 45.0):
        self.base_url = base_url or settings.ai_base_url
        self.model = model or settings.ai_model
        self.api_key = api_key or settings.ai_api_key
        self.timeout = timeout

    def call_json(self, *, system: str, user: str,
                  schema: type[BaseModel]) -> tuple[BaseModel, LLMCallResult]:
        """One validated JSON call: on schema failure, retry ONCE with the
        validation error appended; then raise `LLMUnavailable`. Every call logs
        model/tokens/latency."""
        if not self.api_key:
            raise LLMUnavailable("AI_API_KEY not configured")
        from openai import OpenAI  # provider-agnostic OpenAI-compatible client

        client = OpenAI(base_url=self.base_url, api_key=self.api_key,
                        timeout=self.timeout, max_retries=1)
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        tokens_in = tokens_out = 0
        started = time.monotonic()
        last_error: Exception | None = None
        for attempt in range(1, 3):
            try:
                response = client.chat.completions.create(
                    model=self.model, messages=messages, temperature=0,
                )
            except Exception as exc:  # 429/503/network — client already retried once
                raise LLMUnavailable(f"LLM call failed: {exc}") from exc
            content = response.choices[0].message.content or ""
            if response.usage is not None:
                tokens_in += response.usage.prompt_tokens or 0
                tokens_out += response.usage.completion_tokens or 0
            try:
                parsed = schema.model_validate_json(_extract_json(content))
            except (ValidationError, json.JSONDecodeError) as exc:
                last_error = exc
                messages.append({"role": "assistant", "content": content})
                messages.append({
                    "role": "user",
                    "content": ("Your reply failed schema validation:\n"
                                f"{exc}\nReply again with ONLY a valid JSON object "
                                "matching the schema — no prose, no code fences."),
                })
                continue
            latency_ms = int((time.monotonic() - started) * 1000)
            result = LLMCallResult(
                model=self.model, tokens_in=tokens_in, tokens_out=tokens_out,
                latency_ms=latency_ms, validation_attempts=attempt,
            )
            logger.info("llm call ok model=%s tokens=%d/%d latency=%dms attempts=%d",
                        self.model, tokens_in, tokens_out, latency_ms, attempt)
            return parsed, result
        raise LLMUnavailable(f"LLM output never validated: {last_error}")
