import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Subtask, Task, TaskDependency, TaskLog, User, UserPreference
from app.schemas.project import (
    DependencyCreate,
    PriorityWeights,
    PriorityWeightsRead,
    SubtaskCreate,
    SubtaskRead,
    SubtaskUpdate,
    TaskLogRead,
)
from app.schemas.task import TaskRead
from app.services import priority_store
from app.services import tasks as task_service
from app.services.priority import DEFAULT_WEIGHTS, INACTIVE_STATUSES, normalize_weights

router = APIRouter(tags=["task details"])
CurrentUser = Annotated[User, Depends(get_current_user)]
DB = Annotated[Session, Depends(get_db)]


# ── subtasks ────────────────────────────────────────────────────────────────
def _owned_subtask(db: Session, user: User, subtask_id: uuid.UUID) -> Subtask:
    sub = db.scalar(select(Subtask).where(Subtask.id == subtask_id, Subtask.user_id == user.id))
    if sub is None:
        raise HTTPException(404, "Subtask not found")
    return sub


@router.get("/tasks/{task_id}/subtasks", response_model=list[SubtaskRead])
def list_subtasks(task_id: uuid.UUID, user: CurrentUser, db: DB):
    task_service.get_task(db, user.id, task_id)
    return list(db.scalars(select(Subtask).where(Subtask.task_id == task_id).order_by(Subtask.sort_order, Subtask.created_at)))


@router.post("/tasks/{task_id}/subtasks", response_model=SubtaskRead, status_code=status.HTTP_201_CREATED)
def create_subtask(task_id: uuid.UUID, body: SubtaskCreate, user: CurrentUser, db: DB):
    task_service.get_task(db, user.id, task_id)
    order = (db.scalar(select(func.max(Subtask.sort_order)).where(Subtask.task_id == task_id)) or 0) + 1
    sub = Subtask(user_id=user.id, task_id=task_id, sort_order=order, **body.model_dump())
    db.add(sub)
    task_service.log(db, user.id, task_id, "subtask_added", {"title": sub.title})
    db.commit()
    return sub


@router.patch("/subtasks/{subtask_id}", response_model=SubtaskRead)
def update_subtask(subtask_id: uuid.UUID, body: SubtaskUpdate, user: CurrentUser, db: DB):
    sub = _owned_subtask(db, user, subtask_id)
    changes = body.model_dump(exclude_unset=True)
    if changes.get("title", "x") is None or changes.get("done", True) is None:
        raise HTTPException(422, "title and done cannot be null")
    if changes.get("done") and not sub.done:
        task_service.log(db, user.id, sub.task_id, "subtask_completed", {"title": sub.title})
    for field, value in changes.items():
        setattr(sub, field, value)
    db.commit()
    return sub


@router.delete("/subtasks/{subtask_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subtask(subtask_id: uuid.UUID, user: CurrentUser, db: DB):
    db.delete(_owned_subtask(db, user, subtask_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── dependencies ────────────────────────────────────────────────────────────
@router.post("/tasks/{task_id}/dependencies", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def add_dependency(task_id: uuid.UUID, body: DependencyCreate, user: CurrentUser, db: DB):
    """`task_id` will wait on `depends_on_id`. Cycles are rejected."""
    task = task_service.get_task(db, user.id, task_id)
    prerequisite = task_service.get_task(db, user.id, body.depends_on_id)
    if task.id == prerequisite.id:
        raise HTTPException(422, "A task cannot depend on itself")
    graph = priority_store.load_graph(db, user.id)
    if prerequisite.id in graph.deps.get(task.id, ()):
        raise HTTPException(409, "That dependency already exists")
    if graph.reaches(prerequisite.id, task.id):
        raise HTTPException(422, "That would create a circular dependency")
    db.add(TaskDependency(task_id=task.id, depends_on_id=prerequisite.id, user_id=user.id))
    task_service.log(db, user.id, task.id, "dependency_added", {"depends_on": prerequisite.title})
    db.flush()
    return task_service._finish(db, user.id, task)


@router.delete("/tasks/{task_id}/dependencies/{depends_on_id}", response_model=TaskRead)
def remove_dependency(task_id: uuid.UUID, depends_on_id: uuid.UUID, user: CurrentUser, db: DB):
    task = task_service.get_task(db, user.id, task_id)
    dep = db.scalar(
        select(TaskDependency).where(
            TaskDependency.task_id == task_id,
            TaskDependency.depends_on_id == depends_on_id,
            TaskDependency.user_id == user.id,
        )
    )
    if dep is None:
        raise HTTPException(404, "Dependency not found")
    prerequisite = db.get(Task, depends_on_id)
    db.delete(dep)
    task_service.log(db, user.id, task.id, "dependency_removed", {"depends_on": prerequisite.title if prerequisite else None})
    db.flush()
    # The former prerequisite no longer blocks this task, so its score must be refreshed too.
    if prerequisite:
        priority_store.recompute(db, user.id, [prerequisite])
    return task_service._finish(db, user.id, task)


# ── history ─────────────────────────────────────────────────────────────────
@router.get("/tasks/{task_id}/history", response_model=list[TaskLogRead])
def task_history(task_id: uuid.UUID, user: CurrentUser, db: DB):
    task_service.get_task(db, user.id, task_id)
    return list(
        db.scalars(
            select(TaskLog).where(TaskLog.task_id == task_id, TaskLog.user_id == user.id).order_by(TaskLog.created_at.desc(), TaskLog.id)
        )
    )


# ── priorities ──────────────────────────────────────────────────────────────
@router.get("/priorities", response_model=list[TaskRead])
def ranked_tasks(user: CurrentUser, db: DB, limit: int = 50):
    """Unfinished tasks, highest effective priority first."""
    priority_store.recompute_all(db, user.id)
    tasks = list(
        db.scalars(
            select(Task)
            .where(Task.user_id == user.id, Task.status.not_in(INACTIVE_STATUSES))
            .order_by(Task.priority_score.desc(), Task.created_at)
            .limit(min(max(limit, 1), 200))
        )
    )
    priority_store.recompute(db, user.id, tasks)
    return tasks


@router.get("/preferences/priority-weights", response_model=PriorityWeightsRead)
def read_weights(user: CurrentUser, db: DB):
    pref = db.get(UserPreference, user.id)
    return PriorityWeightsRead(
        weights=priority_store.get_weights(db, user.id),
        defaults=DEFAULT_WEIGHTS,
        is_custom=bool(pref and pref.priority_weights),
    )


@router.put("/preferences/priority-weights", response_model=PriorityWeightsRead)
def set_weights(body: PriorityWeights, user: CurrentUser, db: DB):
    try:
        weights = normalize_weights(body.model_dump())
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    pref = db.get(UserPreference, user.id) or UserPreference(user_id=user.id)
    pref.priority_weights = {k: round(v, 4) for k, v in weights.items()}
    db.add(pref)
    db.commit()
    priority_store.recompute_all(db, user.id)
    return PriorityWeightsRead(weights=pref.priority_weights, defaults=DEFAULT_WEIGHTS, is_custom=True)


@router.delete("/preferences/priority-weights", response_model=PriorityWeightsRead)
def reset_weights(user: CurrentUser, db: DB):
    pref = db.get(UserPreference, user.id)
    if pref:
        pref.priority_weights = None
        db.commit()
    priority_store.recompute_all(db, user.id)
    return PriorityWeightsRead(weights=dict(DEFAULT_WEIGHTS), defaults=DEFAULT_WEIGHTS, is_custom=False)
