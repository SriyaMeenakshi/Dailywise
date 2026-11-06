"""Errors the AI layer raises. Each maps to an HTTP status so routes need no special handling."""


class AIError(Exception):
    status_code = 502
    code = "ai_error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class AINotConfigured(AIError):
    status_code, code = 503, "not_configured"


class AIInputTooLong(AIError):
    status_code, code = 413, "input_too_long"


class AIQuotaExceeded(AIError):
    status_code, code = 429, "quota_exceeded"


class AIBusy(AIError):
    status_code, code = 409, "duplicate_request"


class AIProviderError(AIError):
    status_code, code = 502, "provider_error"


class AIRateLimited(AIError):
    status_code, code = 503, "provider_rate_limited"


class AITimeout(AIError):
    status_code, code = 504, "provider_timeout"


class AIInvalidResponse(AIError):
    status_code, code = 502, "invalid_response"


# What a provider implementation raises; the gateway decides whether to retry.
class ProviderError(Exception):
    """Non-retryable provider failure (bad request, auth)."""


class ProviderRetryable(Exception):
    def __init__(self, message: str, *, kind: str = "unavailable", retry_after: float | None = None):
        super().__init__(message)
        self.kind = kind  # "rate_limited" | "timeout" | "unavailable"
        self.retry_after = retry_after
