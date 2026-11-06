"""Chooses which model serves a feature: economical by default, stronger only where it pays off."""

from app.core.config import Settings

# "simple" = extraction/classification; "complex" = multi-step planning that benefits from reasoning.
FEATURE_TIER = {
    "parse_tasks": "simple",
    "decompose_project": "complex",
}


def model_for(feature: str, settings: Settings) -> str:
    if FEATURE_TIER.get(feature, "simple") == "complex" and settings.ai_model_complex:
        return settings.ai_model_complex
    return settings.ai_model
