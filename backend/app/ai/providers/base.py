from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ProviderRequest:
    model: str
    system: str
    user: str
    max_output_tokens: int
    timeout: float
    temperature: float = 0.2


@dataclass(frozen=True)
class ProviderResponse:
    text: str
    input_tokens: int
    output_tokens: int


class Provider(Protocol):
    """Anything that can turn a prompt into JSON text. Business logic only sees this."""

    def generate(self, request: ProviderRequest) -> ProviderResponse: ...
