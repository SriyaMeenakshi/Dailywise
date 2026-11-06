"""Applies the pure priority engine to stored tasks and keeps the stored score/factors current."""

import uuid
from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Task, TaskDependency, UserPreference
from app.services.priority import INACTIVE_STATUSES, PriorityInput, calculate, normalize_weights


class Graph:
    """The user's dependency graph. `deps[t]` are the tasks `t` waits on."""

    def __init__(self, edges: Iterable[tuple[uuid.UUID, uuid.UUID]], status: dict[uuid.UUID, str]):
        self.status = status
        self.deps: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
        self.dependents: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
        for task_id, depends_on in edges:
            self.deps[task_id].add(depends_on)
            self.dependents[depends_on].add(task_id)

    def active(self, task_id: uuid.UUID) -> bool:
        return self.status.get(task_id, "completed") not in INACTIVE_STATUSES

    def waiting_on(self, task_id: uuid.UUID) -> int:
        return sum(1 for d in self.deps.get(task_id, ()) if self.active(d))

    def blocking(self, task_id: uuid.UUID) -> int:
        return sum(1 for d in self.dependents.get(task_id, ()) if self.active(d))

    def reaches(self, start: uuid.UUID, target: uuid.UUID) -> bool:
        """True if following 'depends on' links from `start` ever arrives at `target`."""
        seen, stack = set(), [start]
        while stack:
            node = stack.pop()
            if node == target:
                return True
            if node not in seen:
                seen.add(node)
                stack.extend(self.deps.get(node, ()))
        return False


def load_graph(db: Session, user_id: uuid.UUID) -> Graph:
    edges = db.execute(
        select(TaskDependency.task_id, TaskDependency.depends_on_id).where(TaskDependency.user_id == user_id)
    ).all()
    status = dict(db.execute(select(Task.id, Task.status).where(Task.user_id == user_id)).all())
    return Graph([(a, b) for a, b in edges], status)


def get_weights(db: Session, user_id: uuid.UUID) -> dict[str, float]:
    pref = db.get(UserPreference, user_id)
    return normalize_weights(pref.priority_weights if pref else None)


def recompute(
    db: Session,
    user_id: uuid.UUID,
    tasks: Iterable[Task],
    *,
    graph: Graph | None = None,
    weights: dict[str, float] | None = None,
    now: datetime | None = None,
) -> None:
    """Refresh stored scores for `tasks` and attach response-only extras. Caller commits."""
    now = now or datetime.now(UTC)
    graph = graph or load_graph(db, user_id)
    weights = weights or get_weights(db, user_id)
    for task in tasks:
        result = calculate(
            PriorityInput(
                importance=task.importance,
                urgency=task.urgency,
                impact=task.impact,
                status=task.status,
                deadline=task.deadline,
                estimated_minutes=task.estimated_minutes,
                blocking_count=graph.blocking(task.id),
                waiting_on_count=graph.waiting_on(task.id),
                override=task.priority_override,
            ),
            weights,
            now,
        )
        if (task.priority_score, task.priority_computed, task.priority_factors) != (
            result.score,
            result.computed,
            result.factors,
        ):
            task.priority_score = result.score
            task.priority_computed = result.computed
            task.priority_factors = result.factors
            task.priority_computed_at = now
        # Response-only attributes (not columns).
        task.priority_explanation = result.explanation
        task.dependency_ids = sorted(graph.deps.get(task.id, ()), key=str)
        task.waiting_on_count = graph.waiting_on(task.id)


def recompute_all(db: Session, user_id: uuid.UUID) -> None:
    tasks = list(db.scalars(select(Task).where(Task.user_id == user_id)))
    recompute(db, user_id, tasks)
    db.commit()
