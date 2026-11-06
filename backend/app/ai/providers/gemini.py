"""Gemini REST provider. All Gemini-specific knowledge lives here and nowhere else."""

import httpx

from app.ai.errors import ProviderError, ProviderRetryable
from app.ai.providers.base import ProviderRequest, ProviderResponse


class GeminiProvider:
    def __init__(self, api_key: str, base_url: str, client: httpx.Client | None = None):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._client = client

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        url = f"{self._base_url}/models/{request.model}:generateContent"
        body = {
            "systemInstruction": {"parts": [{"text": request.system}]},
            "contents": [{"role": "user", "parts": [{"text": request.user}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": request.temperature,
                "maxOutputTokens": request.max_output_tokens,
            },
        }
        # The key goes in a header, never the URL, so it cannot leak into logs or error messages.
        headers = {"x-goog-api-key": self._api_key, "Content-Type": "application/json"}
        try:
            if self._client is not None:
                res = self._client.post(url, json=body, headers=headers, timeout=request.timeout)
            else:
                res = httpx.post(url, json=body, headers=headers, timeout=request.timeout)
        except httpx.TimeoutException:
            raise ProviderRetryable("The AI provider timed out", kind="timeout") from None
        except httpx.HTTPError:
            raise ProviderRetryable("Could not reach the AI provider", kind="unavailable") from None

        if res.status_code == 429:
            retry_after = res.headers.get("retry-after")
            raise ProviderRetryable(
                "The AI provider is rate limiting requests",
                kind="rate_limited",
                retry_after=float(retry_after) if retry_after and retry_after.replace(".", "").isdigit() else None,
            )
        if res.status_code >= 500:
            raise ProviderRetryable(f"The AI provider returned {res.status_code}", kind="unavailable")
        if res.status_code in (401, 403):
            raise ProviderError("The AI provider rejected the API key")
        if res.status_code >= 400:
            raise ProviderError(f"The AI provider rejected the request ({res.status_code})")

        try:
            data = res.json()
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts)
        except (ValueError, KeyError, IndexError, TypeError):
            text = ""  # empty / blocked response: the gateway treats this as invalid and may retry
            data = {}
        usage = data.get("usageMetadata", {}) if isinstance(data, dict) else {}
        return ProviderResponse(
            text=text,
            input_tokens=int(usage.get("promptTokenCount", 0) or 0),
            output_tokens=int(usage.get("candidatesTokenCount", 0) or 0),
        )
