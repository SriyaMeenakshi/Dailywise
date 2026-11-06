"""Shapes the model must return. Deliberately lenient (clamping and cleaning happen afterwards in
services/ai_tasks.py) so a slightly-off answer is repaired rather than wasted."""

from pydantic import BaseModel, Field


class ParsedTask(BaseModel):
    title: str
    description: str | None = None
    category: str | None = None
    deadline: str | None = None
    expected_outcome: str | None = None
    estimated_minutes: int | None = None
    importance: int | None = None


class ParseResult(BaseModel):
    tasks: list[ParsedTask] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)


class DSubtask(BaseModel):
    title: str
    estimated_minutes: int | None = None


class DTask(BaseModel):
    ref: str | None = None
    title: str
    description: str | None = None
    estimated_minutes: int | None = None
    subtasks: list[DSubtask] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)


class DPhase(BaseModel):
    name: str
    milestone: str | None = None
    tasks: list[DTask] = Field(default_factory=list)


class Decomposition(BaseModel):
    project_name: str | None = None
    objective: str | None = None
    phases: list[DPhase] = Field(default_factory=list)
