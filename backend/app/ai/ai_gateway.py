"""The single entry point for model calls. Business code never talks to a provider directly.

Order of operations for every request:
  1. reject over-long input        4. daily request/token quota
  2. serve from cache (free)       5. call the provider, retrying transient failures with backoff
  3. refuse duplicate in-flight    6. validate -> cache -> log tokens, cost, model and prompt version
"""

import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ai import cache_manager, usage_tracker
from app.ai.errors import (
    AIBusy,
    AIError,
    AIInputTooLong,
    AIInvalidResponse,
    AINotConfigured,
    AIProviderError,
    AIQuotaExceeded,
    AIRateLimited,
    AITimeout,
    ProviderError,
    ProviderRetryable,
)
from app.ai.model_router import model_for
from app.ai.prompt_manager import get_prompt
from app.ai.providers.base import Provider, ProviderRequest
from app.ai.response_validator import parse_and_validate
from app.core.config import Settings

T = TypeVar("T", bound=BaseModel)

_inflight: set[tuple[uuid.UUID, str]] = set()
_inflight_lock = threading.Lock()
_MAX_RETRY_AFTER = 30.0
_RETRYABLE_AS = {"rate_limited": AIRateLimited, "timeout": AITimeout, "unavailable": AIProviderError}


@dataclass(frozen=True)
class GatewayResult(Generic[T]):
    data: T
    cached: bool
    model: str
    prompt_version: str


class AIGateway:
    def __init__(
        self,
        settings: Settings,
        provider: Provider | None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.settings = settings
        self.provider = provider
        self._sleep = sleep

    def run(
        self,
        db: Session,
        user_id: uuid.UUID,
        *,
        feature: str,
        input_text: str,
        user_message: str,
        cache_payload: dict,
        schema: type[T],
        force: bool = False,
    ) -> GatewayResult[T]:
        s = self.settings
        prompt = get_prompt(feature)
        model = model_for(feature, s)
        started = time.monotonic()

        if len(input_text) > s.ai_max_input_chars:
            raise AIInputTooLong(f"That is too long for AI processing (limit {s.ai_max_input_chars} characters).")

        key = cache_manager.make_key(feature, prompt.version, model, cache_payload)
        if not force:
            hit = cache_manager.get(db, user_id, key)
            if hit is not None:
                try:
                    data = schema.model_validate(hit)
                except Exception:  # stale shape from an older schema: ignore and regenerate
                    cache_manager.invalidate(db, user_id, key)
                else:
                    usage_tracker.record(db, user_id, feature=feature, model=model, prompt_version=prompt.version,
                                         status="cached", cached=True)
                    return GatewayResult(data, True, model, prompt.version)

        if self.provider is None or not s.ai_configured:
            raise AINotConfigured("AI features are not set up on this server. Everything else still works.")

        with _inflight_lock:
            if (user_id, key) in _inflight:
                raise AIBusy("This exact request is already running. Please wait for it to finish.")
            _inflight.add((user_id, key))
        try:
            usage = usage_tracker.usage_today(db, user_id, s)
            if usage.exhausted:
                raise AIQuotaExceeded("You have reached today's AI limit. It resets at midnight UTC.")
            return self._call(db, user_id, feature, prompt.version, model, key, user_message, prompt.system, schema, started)
        finally:
            with _inflight_lock:
                _inflight.discard((user_id, key))

    def _call(self, db, user_id, feature, version, model, key, user_message, system, schema, started):
        s = self.settings
        request = ProviderRequest(
            model=model, system=system, user=user_message,
            max_output_tokens=s.ai_max_output_tokens, timeout=s.ai_timeout_seconds,
        )
        tokens_in = tokens_out = attempts = 0
        last: AIError | None = None
        for attempt in range(s.ai_max_retries + 1):
            attempts += 1
            try:
                response = self.provider.generate(request)
            except ProviderRetryable as e:
                last = _RETRYABLE_AS.get(e.kind, AIProviderError)(str(e))
                if attempt < s.ai_max_retries:
                    delay = e.retry_after if e.retry_after is not None else s.ai_retry_base_seconds * 2**attempt
                    self._sleep(min(delay, _MAX_RETRY_AFTER))
                continue
            except ProviderError as e:
                last = AIProviderError(str(e))
                break  # retrying a rejected request or bad key cannot help
            tokens_in += response.input_tokens
            tokens_out += response.output_tokens
            try:
                data = parse_and_validate(response.text, schema)
            except AIInvalidResponse as e:
                last = e  # model output is non-deterministic, so another attempt may succeed
                continue
            cost = usage_tracker.estimate_cost(s, tokens_in, tokens_out)
            cache_manager.put(db, user_id, key, feature=feature, model=model, prompt_version=version,
                              response=data.model_dump(mode="json"), ttl_days=s.ai_cache_ttl_days)
            usage_tracker.record(db, user_id, feature=feature, model=model, prompt_version=version, status="ok",
                                 input_tokens=tokens_in, output_tokens=tokens_out, cost_usd=cost,
                                 attempts=attempts, latency_ms=int((time.monotonic() - started) * 1000))
            return GatewayResult(data, False, model, version)

        assert last is not None
        usage_tracker.record(db, user_id, feature=feature, model=model, prompt_version=version, status="error",
                             input_tokens=tokens_in, output_tokens=tokens_out,
                             cost_usd=usage_tracker.estimate_cost(s, tokens_in, tokens_out),
                             error_code=last.code, attempts=attempts,
                             latency_ms=int((time.monotonic() - started) * 1000))
        raise last
