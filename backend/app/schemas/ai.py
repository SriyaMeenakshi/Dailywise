import uuid
from datetime import datetime

from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

from app.schemas.common import UTCDateTime

MAX_PHASES, MAX_TASKS_PER_PHASE, MAX_TASKS_TOTAL, MAX_SUBTASKS = 8, 12, 60, 8


def _text(max_length: int):
    """Strip first, then require something to be left, so whitespace-only text is rejected like ''."""
    return Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=max_length)]


class ParseRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20_000)
    utc_offset_minutes: int = Field(default=0, ge=-840, le=840)  # the user's clock: local = UTC + offset
    force: bool = False

    @field_validator("text")
    @classmethod
    def _strip(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Write something to capture")
        return v.strip()


class SuggestedTask(BaseModel):
    title: str
    description: str | None = None
    category_id: uuid.UUID | None = None
    category_name: str | None = None
    deadline: UTCDateTime | None = None
    deadline_has_time: bool = False
    expected_outcome: str | None = None
    estimated_minutes: int | None = None  # a suggestion from the AI, shown as such
    importance: int | None = None


class ParseResponse(BaseModel):
    tasks: list[SuggestedTask]
    questions: list[str]
    cached: bool
    model: str
    deadlines_removed: bool = False  # the AI proposed dates the note never mentioned; they were dropped


class DecomposeRequest(BaseModel):
    goal: str = Field(min_length=3, max_length=500)
    context: str = Field(default="", max_length=2_000)
    force: bool = False

    @field_validator("goal", "context")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class PlanSubtask(BaseModel):
    title: _text(300)
    estimated_minutes: int | None = Field(default=None, gt=0, le=60 * 24)


class PlanTask(BaseModel):
    ref: _text(40)
    title: _text(300)
    description: str | None = Field(default=None, max_length=2_000)
    estimated_minutes: int | None = Field(default=None, gt=0, le=60 * 24)
    subtasks: list[PlanSubtask] = Field(default_factory=list, max_length=MAX_SUBTASKS)
    depends_on: list[str] = Field(default_factory=list)


class PlanPhase(BaseModel):
    name: _text(200)
    milestone: str | None = Field(default=None, max_length=300)
    tasks: list[PlanTask] = Field(default_factory=list, max_length=MAX_TASKS_PER_PHASE)


class DecomposeBody(BaseModel):
    """What the review screen shows and what the user approves."""

    project_name: _text(200)
    objective: str | None = Field(default=None, max_length=5_000)
    phases: list[PlanPhase] = Field(max_length=MAX_PHASES)

    @model_validator(mode="after")
    def _check_graph(self):
        refs = [t.ref for p in self.phases for t in p.tasks]
        if len(refs) > MAX_TASKS_TOTAL:
            raise ValueError(f"A breakdown can create at most {MAX_TASKS_TOTAL} tasks at once")
        if len(set(refs)) != len(refs):
            raise ValueError("Task references must be unique")
        known = set(refs)
        edges = {t.ref: set(t.depends_on) for p in self.phases for t in p.tasks}
        if any(d not in known for deps in edges.values() for d in deps):
            raise ValueError("A task depends on something that is not in the plan")
        if has_cycle(edges):
            raise ValueError("The plan contains a circular dependency")
        return self


class DecomposeResponse(DecomposeBody):
    cached: bool
    model: str
    truncated: bool = False  # the AI proposed more than we allow and the excess was trimmed


class ApplyRequest(DecomposeBody):
    project_id: uuid.UUID | None = None  # add to this project instead of creating one
    deadline: datetime | None = None


class ApplyResponse(BaseModel):
    project_id: uuid.UUID
    phases_created: int
    tasks_created: int


class AIStatus(BaseModel):
    configured: bool
    model: str | None
    complex_model: str | None
    requests_today: int
    request_limit: int
    tokens_today: int
    token_limit: int
    cost_today_usd: float
    cached_today: int
    cost_tracking: bool  # false until prices are configured, so a 0 is not mistaken for "free"


def has_cycle(edges: dict[str, set[str]]) -> bool:
    WHITE, GREY, BLACK = 0, 1, 2
    colour = {n: WHITE for n in edges}

    def visit(n: str) -> bool:
        colour[n] = GREY
        for m in edges.get(n, ()):
            if colour.get(m) == GREY or (colour.get(m) == WHITE and visit(m)):
                return True
        colour[n] = BLACK
        return False

    return any(colour[n] == WHITE and visit(n) for n in list(edges))
