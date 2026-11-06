from fastapi import Depends

from app.ai.ai_gateway import AIGateway
from app.ai.providers.gemini import GeminiProvider
from app.core.config import Settings, get_settings


def get_gateway(settings: Settings = Depends(get_settings)) -> AIGateway:
    """Tests override this with a gateway that uses a fake provider."""
    provider = GeminiProvider(settings.gemini_api_key, settings.gemini_api_base) if settings.ai_configured else None
    return AIGateway(settings, provider)
