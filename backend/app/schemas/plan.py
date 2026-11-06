import uuid
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


class GenerateRequest(BaseModel):
    date: date
    utc_offset_minutes: int = Field(default=0, ge=-840, le=840)  # local = UTC + offset
    start_after_min: int | None = Field(default=None, ge=0, le=1440)  # e.g. the current time, for today


Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


class FixedBlockCreate(BaseModel):
    date: date
    title: Title
    start_min: int = Field(ge=0, le=1439)
    end_min: int = Field(ge=1, le=1440)

    @model_validator(mode="after")
    def _order(self):
        if self.start_min >= self.end_min:
            raise ValueError("The block must end after it starts")
        return self


class BlockUpdate(BaseModel):
    start_min: int | None = Field(default=None, ge=0, le=1439)
    end_min: int | None = Field(default=None, ge=1, le=1440)
    done: bool | None = None
    title: Title | None = None


class MoveRequest(BaseModel):
    direction: Literal["up", "down"]


class BlockRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID | None
    plan_date: date
    kind: Literal["task", "break", "fixed", "postponed"]
    title: str | None
    start_min: int
    end_min: int
    pinned: bool
    done: bool
    warning: str | None
    priority_level: str | None = None


class UnscheduledRead(BaseModel):
    task_id: uuid.UUID
    title: str
    reason: str


class PlanRead(BaseModel):
    date: date
    window_start: int
    window_end: int
    break_minutes: int
    blocks: list[BlockRead]
    unscheduled: list[UnscheduledRead] = []
    unscheduled_total: int = 0
    planned_minutes: int = 0
    free_minutes: int = 0


class PlannerPrefs(BaseModel):
    workday_start_min: int = Field(ge=0, le=1439)
    workday_end_min: int = Field(ge=1, le=1440)
    break_minutes: int = Field(ge=0, le=60)

    @model_validator(mode="after")
    def _sane(self):
        if self.workday_end_min - self.workday_start_min < 30:
            raise ValueError("Your available time must be at least 30 minutes long")
        return self
