import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.schemas.common import UTCDateTime
from app.services.priority import level_for

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
    project_id: uuid.UUID | None = None
    phase_id: uuid.UUID | None = None
    importance: int = Field(default=3, ge=1, le=5)
    urgency: int = Field(default=3, ge=1, le=5)
    impact: int = Field(default=3, ge=1, le=5)
    priority_override: int | None = Field(default=None, ge=0, le=100)
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
    project_id: uuid.UUID | None = None
    phase_id: uuid.UUID | None = None
    importance: int | None = Field(default=None, ge=1, le=5)
    urgency: int | None = Field(default=None, ge=1, le=5)
    impact: int | None = Field(default=None, ge=1, le=5)
    priority_override: int | None = Field(default=None, ge=0, le=100)
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


class PriorityFactor(BaseModel):
    key: str
    label: str
    value: float
    weight: float
    contribution: float


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None
    expected_outcome: str | None
    notes: str | None
    category_id: uuid.UUID | None
    project_id: uuid.UUID | None
    phase_id: uuid.UUID | None
    importance: int
    urgency: int
    impact: int
    energy: Energy
    status: TaskStatus
    recurrence: Recurrence
    deadline: UTCDateTime | None
    estimated_minutes: int | None
    actual_minutes: int | None
    completed_at: UTCDateTime | None
    created_at: UTCDateTime
    updated_at: UTCDateTime
    priority_score: float
    priority_computed: float
    priority_override: int | None
    priority_factors: list[PriorityFactor] | None = None
    priority_explanation: str | None = None
    dependency_ids: list[uuid.UUID] = []
    waiting_on_count: int = 0

    @computed_field
    @property
    def priority_level(self) -> str:
        return level_for(self.priority_score)
