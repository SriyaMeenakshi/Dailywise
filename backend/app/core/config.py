from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    database_url: str = "sqlite:///./daywise_dev.db"
    supabase_url: str = ""
    supabase_jwt_secret: str = ""
    allowed_origins: str = "http://localhost:3000"

    # ── AI (all optional: the app works fully without them) ────────────────────
    gemini_api_key: str = ""
    gemini_api_base: str = "https://generativelanguage.googleapis.com/v1beta"
    ai_model: str = "gemini-2.5-flash"  # economical model for simple extraction
    ai_model_complex: str = ""  # stronger model for decomposition; falls back to ai_model
    ai_daily_request_limit: int = 30  # provider calls per user per UTC day (cache hits are free)
    ai_daily_token_limit: int = 200_000  # input + output tokens per user per UTC day
    ai_max_input_chars: int = 4_000
    ai_max_output_tokens: int = 4_096
    ai_timeout_seconds: float = 30.0
    ai_max_retries: int = 2  # retries after the first attempt, with exponential backoff
    ai_retry_base_seconds: float = 1.0
    ai_cache_ttl_days: int = 30
    # Estimated cost = tokens x these prices. Left at 0 on purpose: set them from your provider's
    # current price list, otherwise reported costs stay 0 rather than being made up.
    ai_price_input_per_mtok: float = 0.0
    ai_price_output_per_mtok: float = 0.0

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    def production_problems(self) -> list[str]:
        """Misconfigurations that must stop a production server from starting."""
        problems = []
        if self.database_url.startswith("sqlite"):
            problems.append("DATABASE_URL must point at PostgreSQL, not SQLite")
        if not self.supabase_url:
            problems.append("SUPABASE_URL is required to verify sign-in tokens")
        origins = self.cors_origins
        if not origins or any(o == "*" or "localhost" in o or "127.0.0.1" in o for o in origins):
            problems.append("ALLOWED_ORIGINS must list your deployed frontend URL (no wildcard or localhost)")
        return problems

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def jwt_issuer(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/auth/v1" if self.supabase_url else ""

    @property
    def jwks_url(self) -> str:
        return f"{self.jwt_issuer}/.well-known/jwks.json" if self.supabase_url else ""

    @property
    def ai_configured(self) -> bool:
        return bool(self.gemini_api_key and self.ai_model)


@lru_cache
def get_settings() -> Settings:
    return Settings()
