import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin

TASK_STATUSES = ("inbox", "not_started", "in_progress", "completed", "blocked", "archived")
ENERGY_LEVELS = ("low", "medium", "high")
RECURRENCES = ("none", "daily", "weekly", "weekdays", "monthly")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class Task(TimestampMixin, Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint(_in("status", TASK_STATUSES), name="ck_tasks_status"),
        CheckConstraint(_in("energy", ENERGY_LEVELS), name="ck_tasks_energy"),
        CheckConstraint(_in("recurrence", RECURRENCES), name="ck_tasks_recurrence"),
        CheckConstraint("importance BETWEEN 1 AND 5", name="ck_tasks_importance"),
        CheckConstraint("urgency BETWEEN 1 AND 5", name="ck_tasks_urgency"),
        CheckConstraint("impact BETWEEN 1 AND 5", name="ck_tasks_impact"),
        CheckConstraint(
            "priority_override IS NULL OR priority_override BETWEEN 0 AND 100",
            name="ck_tasks_priority_override",
        ),
        CheckConstraint(
            "estimated_minutes IS NULL OR estimated_minutes > 0", name="ck_tasks_estimate"
        ),
        CheckConstraint("actual_minutes IS NULL OR actual_minutes >= 0", name="ck_tasks_actual"),
        Index("ix_tasks_user_status", "user_id", "status"),
        Index("ix_tasks_user_deadline", "user_id", "deadline"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("categories.id", ondelete="SET NULL"), index=True
    )

    project_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="SET NULL"), index=True
    )
    phase_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("project_phases.id", ondelete="SET NULL"), index=True
    )

    # Priority: `priority_computed` is the engine's score; `priority_score` is what the user
    # sees (the override when set). Factors are stored so the score can always be explained.
    impact: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    priority_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    priority_computed: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    priority_override: Mapped[int | None] = mapped_column(Integer)
    priority_factors: Mapped[list | None] = mapped_column(JSON)
    priority_computed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    expected_outcome: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

    importance: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    urgency: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    energy: Mapped[str] = mapped_column(String(10), nullable=False, default="medium")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="inbox")
    recurrence: Mapped[str] = mapped_column(String(10), nullable=False, default="none")

    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    estimated_minutes: Mapped[int | None] = mapped_column(Integer)
    actual_minutes: Mapped[int | None] = mapped_column(Integer)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user = relationship("User", back_populates="tasks")
    category = relationship("Category")
