import uuid
from datetime import date

from pydantic import BaseModel, Field

from app.schemas.common import UTCDateTime


class TaskBrief(BaseModel):
    id: uuid.UUID
    title: str
    deadline: UTCDateTime | None = None
    estimated_minutes: int | None = None
    actual_minutes: int | None = None
    priority_level: str | None = None


class ReviewText(BaseModel):
    accomplished: str = Field(default="", max_length=5_000)
    remaining: str = Field(default="", max_length=5_000)
    blockers: str = Field(default="", max_length=5_000)
    tomorrow_focus: str = Field(default="", max_length=5_000)


class ReviewFacts(BaseModel):
    """Computed from real task data, never invented."""

    completed: list[TaskBrief]
    completed_minutes: int
    remaining: list[TaskBrief]  # unfinished and due on or before this day
    blocked: list[TaskBrief]
    suggested_tomorrow: list[TaskBrief]  # highest-priority unfinished tasks, from the priority engine


class ReviewRead(BaseModel):
    date: date
    saved: ReviewText | None  # null until the user writes something
    facts: ReviewFacts


class DayPoint(BaseModel):
    date: date
    completed: int
    completed_minutes: int


class CategoryProgress(BaseModel):
    name: str
    color: str
    completed: int
    pending: int


class TimeAccuracy(BaseModel):
    tasks: int  # completed tasks in the period that have both an estimate and an actual
    estimated_minutes: int
    actual_minutes: int
    biggest_misses: list[TaskBrief]


class ProjectBrief(BaseModel):
    id: uuid.UUID
    name: str
    percent: float
    remaining_minutes: int
    deadline: UTCDateTime | None


class Analytics(BaseModel):
    days: int
    completed: int
    pending: int
    overdue: int
    blocked: int
    completed_with_deadline: int
    completed_on_time: int
    daily: list[DayPoint]
    by_category: list[CategoryProgress]
    time_accuracy: TimeAccuracy
    projects: list[ProjectBrief]
