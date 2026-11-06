import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import AIUsageLog


@dataclass(frozen=True)
class Usage:
    requests_today: int
    tokens_today: int
    cost_today_usd: float
    cached_today: int
    request_limit: int
    token_limit: int

    @property
    def requests_left(self) -> int:
        return max(self.request_limit - self.requests_today, 0)

    @property
    def tokens_left(self) -> int:
        return max(self.token_limit - self.tokens_today, 0)

    @property
    def exhausted(self) -> bool:
        return self.requests_today >= self.request_limit or self.tokens_today >= self.token_limit


def estimate_cost(settings: Settings, input_tokens: int, output_tokens: int) -> float:
    return (
        input_tokens * settings.ai_price_input_per_mtok + output_tokens * settings.ai_price_output_per_mtok
    ) / 1_000_000


def usage_today(db: Session, user_id: uuid.UUID, settings: Settings) -> Usage:
    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    # Compare in naive UTC: SQLite stores naive values and Postgres accepts them for timestamptz.
    rows = db.execute(
        select(
            AIUsageLog.cached,
            func.count(),
            func.coalesce(func.sum(AIUsageLog.input_tokens + AIUsageLog.output_tokens), 0),
            func.coalesce(func.sum(AIUsageLog.cost_usd), 0.0),
        )
        .where(AIUsageLog.user_id == user_id, AIUsageLog.created_at >= start)
        .group_by(AIUsageLog.cached)
    ).all()
    live = next(((c, t, cost) for cached, c, t, cost in rows if not cached), (0, 0, 0.0))
    cached = next((c for cached, c, _t, _cost in rows if cached), 0)
    return Usage(live[0], int(live[1]), float(live[2]), cached, settings.ai_daily_request_limit, settings.ai_daily_token_limit)


def record(
    db: Session, user_id: uuid.UUID, *, feature: str, model: str, prompt_version: str, status: str,
    input_tokens: int = 0, output_tokens: int = 0, cost_usd: float = 0.0, cached: bool = False,
    error_code: str | None = None, attempts: int = 1, latency_ms: int = 0,
) -> None:
    db.add(AIUsageLog(
        user_id=user_id, feature=feature, model=model, prompt_version=prompt_version, status=status,
        input_tokens=input_tokens, output_tokens=output_tokens, cost_usd=cost_usd, cached=cached,
        error_code=error_code, attempts=attempts, latency_ms=latency_ms,
    ))
    db.commit()
