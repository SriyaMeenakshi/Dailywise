import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

TaskStatus = Literal["inbox", "not_started", "in_progress", "completed", "blocked", "archived"]
Energy = Literal["low", "medium", "high"]
Recurrence = Literal["none", "daily", "weekly", "weekdays", "monthly"]

_MAX_MINUTES = 60 * 24 * 14


def _clean_title(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Title cannot be blank")
    return value


class TaskCreate(BaseModel):
    """Only `title` is required; everything else has a sensible default."""

    title: str = Field(max_length=300)
    description: str | None = Field(default=None, max_length=10_000)
    expected_outcome: str | None = Field(default=None, max_length=2_000)
    notes: str | None = Field(default=None, max_length=10_000)
    category_id: uuid.UUID | None = None
    importance: int = Field(default=3, ge=1, le=5)
    urgency: int = Field(default=3, ge=1, le=5)
    energy: Energy = "medium"
    status: TaskStatus = "inbox"
    recurrence: Recurrence = "none"
    deadline: datetime | None = None
    estimated_minutes: int | None = Field(default=None, gt=0, le=_MAX_MINUTES)
    actual_minutes: int | None = Field(default=None, ge=0, le=_MAX_MINUTES)

    _title = field_validator("title")(_clean_title)


class TaskUpdate(BaseModel):
    """Partial update: only fields present in the request body are changed."""

    title: str | None = Field(default=None, max_length=300)
    description: str | None = Field(default=None, max_length=10_000)
    expected_outcome: str | None = Field(default=None, max_length=2_000)
    notes: str | None = Field(default=None, max_length=10_000)
    category_id: uuid.UUID | None = None
    importance: int | None = Field(default=None, ge=1, le=5)
    urgency: int | None = Field(default=None, ge=1, le=5)
    energy: Energy | None = None
    status: TaskStatus | None = None
    recurrence: Recurrence | None = None
    deadline: datetime | None = None
    estimated_minutes: int | None = Field(default=None, gt=0, le=_MAX_MINUTES)
    actual_minutes: int | None = Field(default=None, ge=0, le=_MAX_MINUTES)

    @field_validator("title")
    @classmethod
    def _title(cls, value: str | None) -> str | None:
        return None if value is None else _clean_title(value)


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None
    expected_outcome: str | None
    notes: str | None
    category_id: uuid.UUID | None
    importance: int
    urgency: int
    energy: Energy
    status: TaskStatus
    recurrence: Recurrence
    deadline: datetime | None
    estimated_minutes: int | None
    actual_minutes: int | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
