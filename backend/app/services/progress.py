"""Effort-weighted progress. Pure functions.

Each task weighs as much as its estimated effort, so finishing a 4-hour task moves the bar more
than finishing a 10-minute one. Tasks with no estimate count as DEFAULT_TASK_MINUTES and are
reported, so the number is never silently invented.
"""

from dataclasses import dataclass, field

DEFAULT_TASK_MINUTES = 30
DEFAULT_SUBTASK_MINUTES = 15


@dataclass(frozen=True)
class SubtaskInfo:
    done: bool
    estimated_minutes: int | None = None


@dataclass(frozen=True)
class TaskInfo:
    status: str
    estimated_minutes: int | None = None
    subtasks: list[SubtaskInfo] = field(default_factory=list)


@dataclass(frozen=True)
class Progress:
    percent: float
    total_minutes: int
    done_minutes: int
    remaining_minutes: int
    tasks_total: int
    tasks_done: int
    unestimated_tasks: int


def task_completion(task: TaskInfo) -> float:
    """0..1. Completed = 1; otherwise the effort-weighted share of finished subtasks."""
    if task.status == "completed":
        return 1.0
    if not task.subtasks:
        return 0.0
    weights = [s.estimated_minutes or DEFAULT_SUBTASK_MINUTES for s in task.subtasks]
    done = sum(w for s, w in zip(task.subtasks, weights) if s.done)
    return done / sum(weights)


def compute_progress(tasks: list[TaskInfo]) -> Progress:
    counted = [t for t in tasks if t.status != "archived"]
    total = done = 0.0
    for t in counted:
        weight = t.estimated_minutes or DEFAULT_TASK_MINUTES
        total += weight
        done += weight * task_completion(t)
    percent = round(done / total * 100, 1) if total else 0.0
    return Progress(
        percent=percent,
        total_minutes=round(total),
        done_minutes=round(done),
        remaining_minutes=round(total - done),
        tasks_total=len(counted),
        tasks_done=sum(1 for t in counted if t.status == "completed"),
        unestimated_tasks=sum(1 for t in counted if not t.estimated_minutes),
    )
