import json
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.ai.errors import AIInvalidResponse

T = TypeVar("T", bound=BaseModel)
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def parse_and_validate(text: str, schema: type[T]) -> T:
    """Turn raw model text into a validated object, or raise AIInvalidResponse."""
    cleaned = _FENCE.sub("", (text or "").strip()).strip()
    if not cleaned:
        raise AIInvalidResponse("The AI returned an empty response")
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        raise AIInvalidResponse("The AI returned something that is not valid JSON") from None
    try:
        return schema.model_validate(data)
    except ValidationError:
        raise AIInvalidResponse("The AI response did not have the expected structure") from None
