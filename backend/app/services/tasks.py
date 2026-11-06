import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Category, Phase, Project, Task, TaskLog
from app.schemas.task import TaskCreate, TaskUpdate
from app.services import priority_store

SORTABLE = {
    "created_at": Task.created_at,
    "updated_at": Task.updated_at,
    "deadline": Task.deadline,
    "importance": Task.importance,
    "urgency": Task.urgency,
    "priority": Task.priority_score,
    "title": Task.title,
}
NOT_NULL_FIELDS = {"title", "importance", "urgency", "impact", "energy", "status", "recurrence"}
LOGGED_FIELDS = (
    "title", "status", "importance", "urgency", "impact", "deadline", "estimated_minutes",
    "actual_minutes", "category_id", "project_id", "phase_id", "priority_override", "energy", "recurrence",
)


def log(db: Session, user_id: uuid.UUID, task_id: uuid.UUID, action: str, detail: dict | None = None) -> None:
    db.add(TaskLog(user_id=user_id, task_id=task_id, action=action, detail=detail))


def _ensure_category_owned(db: Session, user_id: uuid.UUID, category_id: uuid.UUID | None) -> None:
    if category_id is None:
        return
    owned = db.scalar(select(Category.id).where(Category.id == category_id, Category.user_id == user_id))
    if owned is None:
        raise HTTPException(422, "Unknown category")


def _resolve_project_phase(
    db: Session, user_id: uuid.UUID, project_id: uuid.UUID | None, phase_id: uuid.UUID | None
) -> tuple[uuid.UUID | None, uuid.UUID | None]:
    """Validate ownership and keep the phase inside its project."""
    if project_id is not None and not db.scalar(
        select(Project.id).where(Project.id == project_id, Project.user_id == user_id)
    ):
        raise HTTPException(422, "Unknown project")
    if phase_id is not None:
        phase = db.scalar(select(Phase).where(Phase.id == phase_id, Phase.user_id == user_id))
        if phase is None:
            raise HTTPException(422, "Unknown phase")
        if project_id is None:
            project_id = phase.project_id
        elif phase.project_id != project_id:
            raise HTTPException(422, "That phase belongs to a different project")
    return project_id, phase_id


def _apply_completion(task: Task) -> None:
    if task.status == "completed":
        task.completed_at = task.completed_at or datetime.now(UTC)
    else:
        task.completed_at = None


def _jsonable(value):
    return value.isoformat() if isinstance(value, datetime) else str(value) if isinstance(value, uuid.UUID) else value


def list_tasks(
    db: Session,
    user_id: uuid.UUID,
    *,
    statuses: list[str] | None,
    category_id: uuid.UUID | None,
    project_id: uuid.UUID | None,
    q: str | None,
    sort: str,
    descending: bool,
    limit: int,
    offset: int,
) -> list[Task]:
    # Scores depend on the clock (deadline risk), so refresh them before sorting or returning.
    priority_store.recompute_all(db, user_id)

    stmt = select(Task).where(Task.user_id == user_id)
    stmt = stmt.where(Task.status.in_(statuses)) if statuses else stmt.where(Task.status != "archived")
    if category_id:
        stmt = stmt.where(Task.category_id == category_id)
    if project_id:
        stmt = stmt.where(Task.project_id == project_id)
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(or_(Task.title.ilike(pattern), Task.description.ilike(pattern)))
    column = SORTABLE[sort]
    order = column.desc() if descending else column.asc()
    # Keep tasks without a value (e.g. no deadline) at the end regardless of direction.
    stmt = stmt.order_by(column.is_(None), order, Task.created_at.desc())
    tasks = list(db.scalars(stmt.limit(limit).offset(offset)))
    priority_store.recompute(db, user_id, tasks)  # attaches response extras
    return tasks


def get_task(db: Session, user_id: uuid.UUID, task_id: uuid.UUID, *, refresh: bool = False) -> Task:
    task = db.scalar(select(Task).where(Task.id == task_id, Task.user_id == user_id))
    if task is None:
        raise HTTPException(404, "Task not found")
    if refresh:
        priority_store.recompute(db, user_id, [task])
        db.commit()
    return task


def _finish(db: Session, user_id: uuid.UUID, task: Task) -> Task:
    """Recompute this task and its prerequisites (whose blocking factor may have changed)."""
    graph = priority_store.load_graph(db, user_id)
    related = [task.id, *graph.deps.get(task.id, ())]
    tasks = list(db.scalars(select(Task).where(Task.id.in_(related), Task.user_id == user_id)))
    priority_store.recompute(db, user_id, tasks, graph=graph)
    db.commit()
    return task


def create_task(db: Session, user_id: uuid.UUID, data: TaskCreate) -> Task:
    _ensure_category_owned(db, user_id, data.category_id)
    values = data.model_dump()
    values["project_id"], values["phase_id"] = _resolve_project_phase(db, user_id, data.project_id, data.phase_id)
    task = Task(user_id=user_id, **values)
    _apply_completion(task)
    db.add(task)
    db.flush()
    log(db, user_id, task.id, "created", {"title": task.title})
    return _finish(db, user_id, task)


def update_task(db: Session, user_id: uuid.UUID, task_id: uuid.UUID, data: TaskUpdate) -> Task:
    task = get_task(db, user_id, task_id)
    changes = data.model_dump(exclude_unset=True)
    for field in NOT_NULL_FIELDS & changes.keys():
        if changes[field] is None:
            raise HTTPException(422, f"{field} cannot be null")
    if "category_id" in changes:
        _ensure_category_owned(db, user_id, changes["category_id"])

    if {"project_id", "phase_id"} & changes.keys():
        project_id = changes.get("project_id", task.project_id)
        phase_id = changes.get("phase_id", task.phase_id)
        if "project_id" in changes and "phase_id" not in changes and project_id != task.project_id:
            phase_id = None  # moving to another project drops the old phase
        changes["project_id"], changes["phase_id"] = _resolve_project_phase(db, user_id, project_id, phase_id)

    diff = {}
    for field, value in changes.items():
        old = getattr(task, field)
        if old != value:
            diff[field] = {"from": _jsonable(old), "to": _jsonable(value)}
        setattr(task, field, value)
    _apply_completion(task)
    if diff:
        action = "status_changed" if "status" in diff else "updated"
        log(db, user_id, task.id, action, diff)
    return _finish(db, user_id, task)


def delete_task(db: Session, user_id: uuid.UUID, task_id: uuid.UUID) -> None:
    task = get_task(db, user_id, task_id)
    prerequisites = list(priority_store.load_graph(db, user_id).deps.get(task.id, ()))
    db.delete(task)
    db.flush()
    if prerequisites:
        priority_store.recompute(
            db, user_id, list(db.scalars(select(Task).where(Task.id.in_(prerequisites))))
        )
    db.commit()
