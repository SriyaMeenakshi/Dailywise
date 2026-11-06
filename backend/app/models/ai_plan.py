import uuid
from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import TimestampMixin


def _now() -> datetime:
    return datetime.now(UTC)


class AIUsageLog(Base):
    """One row per gateway call: provider calls (counted against quotas) and cache hits (free)."""

    __tablename__ = "ai_usage_logs"
    __table_args__ = (Index("ix_ai_usage_user_created", "user_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    feature: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(20), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cached: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # ok | cached | error
    error_code: Mapped[str | None] = mapped_column(String(40))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now(), nullable=False
    )


class AICache(Base):
    """Validated model output, scoped to the user who requested it."""

    __tablename__ = "ai_cache"
    __table_args__ = (UniqueConstraint("user_id", "cache_key", name="uq_ai_cache_user_key"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    cache_key: Mapped[str] = mapped_column(String(64), nullable=False)
    feature: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(20), nullable=False)
    response: Mapped[dict] = mapped_column(JSON, nullable=False)
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DailyReview(TimestampMixin, Base):
    """The user's own end-of-day reflection. Facts (what was completed etc.) are computed, not stored."""

    __tablename__ = "daily_reviews"
    __table_args__ = (UniqueConstraint("user_id", "review_date", name="uq_daily_reviews_user_date"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    review_date: Mapped[date] = mapped_column(Date, nullable=False)
    accomplished: Mapped[str | None] = mapped_column(Text)
    remaining: Mapped[str | None] = mapped_column(Text)
    blockers: Mapped[str | None] = mapped_column(Text)
    tomorrow_focus: Mapped[str | None] = mapped_column(Text)


class ScheduleBlock(TimestampMixin, Base):
    """A slice of a day. Times are minutes from local midnight, so no timezone maths is needed."""

    __tablename__ = "schedule_blocks"
    __table_args__ = (
        CheckConstraint("kind IN ('task', 'break', 'fixed', 'postponed')", name="ck_schedule_blocks_kind"),
        CheckConstraint(
            "start_min >= 0 AND end_min <= 1440 AND start_min < end_min", name="ck_schedule_blocks_range"
        ),
        Index("ix_schedule_blocks_user_date", "user_id", "plan_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    task_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    plan_date: Mapped[date] = mapped_column(Date, nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    title: Mapped[str | None] = mapped_column(String(300))
    start_min: Mapped[int] = mapped_column(Integer, nullable=False)
    end_min: Mapped[int] = mapped_column(Integer, nullable=False)
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    warning: Mapped[str | None] = mapped_column(String(300))
