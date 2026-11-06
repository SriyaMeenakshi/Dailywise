import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import UTCDateTime

ProjectStatus = Literal["active", "on_hold", "completed", "archived"]


def _name(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Name cannot be blank")
    return value


class ProjectCreate(BaseModel):
    name: str = Field(max_length=200)
    objective: str | None = Field(default=None, max_length=5_000)
    deadline: datetime | None = None
    status: ProjectStatus = "active"

    _name = field_validator("name")(_name)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    objective: str | None = Field(default=None, max_length=5_000)
    deadline: datetime | None = None
    status: ProjectStatus | None = None

    @field_validator("name")
    @classmethod
    def _n(cls, value: str | None) -> str | None:
        return None if value is None else _name(value)


class ProgressRead(BaseModel):
    percent: float
    total_minutes: int
    done_minutes: int
    remaining_minutes: int
    tasks_total: int
    tasks_done: int
    unestimated_tasks: int


class PhaseCreate(BaseModel):
    name: str = Field(max_length=200)

    _name = field_validator("name")(_name)


class PhaseUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    sort_order: int | None = None

    @field_validator("name")
    @classmethod
    def _n(cls, value: str | None) -> str | None:
        return None if value is None else _name(value)


class PhaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    sort_order: int
    milestone: str | None = None
    progress: ProgressRead | None = None
    earliest_deadline: UTCDateTime | None = None
    latest_deadline: UTCDateTime | None = None


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    objective: str | None
    status: ProjectStatus
    deadline: UTCDateTime | None
    created_at: UTCDateTime
    updated_at: UTCDateTime
    progress: ProgressRead | None = None
    phases: list[PhaseRead] = []
    unphased_progress: ProgressRead | None = None


class SubtaskCreate(BaseModel):
    title: str = Field(max_length=300)
    estimated_minutes: int | None = Field(default=None, gt=0, le=60 * 24)

    _title = field_validator("title")(_name)


class SubtaskUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    estimated_minutes: int | None = Field(default=None, gt=0, le=60 * 24)
    done: bool | None = None

    @field_validator("title")
    @classmethod
    def _t(cls, value: str | None) -> str | None:
        return None if value is None else _name(value)


class SubtaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    title: str
    estimated_minutes: int | None
    done: bool
    sort_order: int


class DependencyCreate(BaseModel):
    depends_on_id: uuid.UUID


class TaskLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    action: str
    detail: dict | None
    created_at: UTCDateTime


class PriorityWeights(BaseModel):
    importance: float = Field(ge=0)
    urgency: float = Field(ge=0)
    deadline: float = Field(ge=0)
    impact: float = Field(ge=0)
    blocking: float = Field(ge=0)


class PriorityWeightsRead(BaseModel):
    weights: dict[str, float]
    defaults: dict[str, float]
    is_custom: bool
