"""The Gemini provider against a mocked HTTP transport (no network, no credits)."""

import json

import httpx
import pytest

from app.ai.errors import ProviderError, ProviderRetryable
from app.ai.providers.base import ProviderRequest
from app.ai.providers.gemini import GeminiProvider

REQ = ProviderRequest(model="m1", system="SYS", user="USER", max_output_tokens=99, timeout=5)


def provider(handler):
    return GeminiProvider("secret-key", "https://example.test/v1beta", httpx.Client(transport=httpx.MockTransport(handler)))


def ok(text='{"a":1}', usage=None):
    body = {"candidates": [{"content": {"parts": [{"text": text}]}}]}
    if usage is not None:
        body["usageMetadata"] = usage
    return httpx.Response(200, json=body)


def test_request_shape_and_key_in_header_not_url():
    seen = {}

    def handler(request):
        seen["url"], seen["headers"], seen["body"] = str(request.url), request.headers, json.loads(request.content)
        return ok(usage={"promptTokenCount": 12, "candidatesTokenCount": 7})

    res = provider(handler).generate(REQ)
    assert seen["url"] == "https://example.test/v1beta/models/m1:generateContent"
    assert "secret-key" not in seen["url"] and seen["headers"]["x-goog-api-key"] == "secret-key"
    body = seen["body"]
    assert body["systemInstruction"]["parts"][0]["text"] == "SYS"
    assert body["contents"][0]["parts"][0]["text"] == "USER"
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert body["generationConfig"]["maxOutputTokens"] == 99
    assert (res.text, res.input_tokens, res.output_tokens) == ('{"a":1}', 12, 7)


def test_missing_usage_metadata_defaults_to_zero():
    res = provider(lambda r: ok()).generate(REQ)
    assert (res.input_tokens, res.output_tokens) == (0, 0)


@pytest.mark.parametrize("body", [{}, {"candidates": []}, {"promptFeedback": {"blockReason": "SAFETY"}}])
def test_blocked_or_empty_candidates_yield_empty_text(body):
    assert provider(lambda r: httpx.Response(200, json=body)).generate(REQ).text == ""


def test_non_json_200_yields_empty_text():
    assert provider(lambda r: httpx.Response(200, text="<html>")).generate(REQ).text == ""


def test_429_is_retryable_with_retry_after():
    with pytest.raises(ProviderRetryable) as e:
        provider(lambda r: httpx.Response(429, headers={"retry-after": "7"})).generate(REQ)
    assert e.value.kind == "rate_limited" and e.value.retry_after == 7.0


def test_5xx_is_retryable():
    with pytest.raises(ProviderRetryable) as e:
        provider(lambda r: httpx.Response(503)).generate(REQ)
    assert e.value.kind == "unavailable"


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_client_errors_are_not_retryable(status):
    with pytest.raises(ProviderError):
        provider(lambda r: httpx.Response(status, json={"error": "x"})).generate(REQ)


def test_timeout_and_network_errors_are_retryable():
    def timeout(request):
        raise httpx.ReadTimeout("slow")

    def network(request):
        raise httpx.ConnectError("down")

    with pytest.raises(ProviderRetryable) as e1:
        provider(timeout).generate(REQ)
    with pytest.raises(ProviderRetryable) as e2:
        provider(network).generate(REQ)
    assert (e1.value.kind, e2.value.kind) == ("timeout", "unavailable")


def test_api_key_never_appears_in_error_messages():
    with pytest.raises(ProviderError) as e:
        provider(lambda r: httpx.Response(401, json={"error": "bad secret-key"})).generate(REQ)
    assert "secret-key" not in str(e.value)
