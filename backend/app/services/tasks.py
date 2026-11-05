import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Category, Task
from app.schemas.task import TaskCreate, TaskUpdate

SORTABLE = {
    "created_at": Task.created_at,
    "updated_at": Task.updated_at,
    "deadline": Task.deadline,
    "importance": Task.importance,
    "urgency": Task.urgency,
    "title": Task.title,
}
NOT_NULL_FIELDS = {"title", "importance", "urgency", "energy", "status", "recurrence"}


def _ensure_category_owned(db: Session, user_id: uuid.UUID, category_id: uuid.UUID | None) -> None:
    if category_id is None:
        return
    owned = db.scalar(
        select(Category.id).where(Category.id == category_id, Category.user_id == user_id)
    )
    if owned is None:
        raise HTTPException(422, "Unknown category")


def _apply_completion(task: Task) -> None:
    if task.status == "completed":
        task.completed_at = task.completed_at or datetime.now(UTC)
    else:
        task.completed_at = None


def list_tasks(
    db: Session,
    user_id: uuid.UUID,
    *,
    statuses: list[str] | None,
    category_id: uuid.UUID | None,
    q: str | None,
    sort: str,
    descending: bool,
    limit: int,
    offset: int,
) -> list[Task]:
    stmt = select(Task).where(Task.user_id == user_id)
    if statuses:
        stmt = stmt.where(Task.status.in_(statuses))
    else:
        stmt = stmt.where(Task.status != "archived")
    if category_id:
        stmt = stmt.where(Task.category_id == category_id)
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(or_(Task.title.ilike(pattern), Task.description.ilike(pattern)))
    column = SORTABLE[sort]
    order = column.desc() if descending else column.asc()
    # Keep tasks without a value (e.g. no deadline) at the end regardless of direction.
    stmt = stmt.order_by(column.is_(None), order, Task.created_at.desc())
    return list(db.scalars(stmt.limit(limit).offset(offset)))


def get_task(db: Session, user_id: uuid.UUID, task_id: uuid.UUID) -> Task:
    task = db.scalar(select(Task).where(Task.id == task_id, Task.user_id == user_id))
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    return task


def create_task(db: Session, user_id: uuid.UUID, data: TaskCreate) -> Task:
    _ensure_category_owned(db, user_id, data.category_id)
    task = Task(user_id=user_id, **data.model_dump())
    _apply_completion(task)
    db.add(task)
    db.commit()
    return task


def update_task(db: Session, user_id: uuid.UUID, task_id: uuid.UUID, data: TaskUpdate) -> Task:
    task = get_task(db, user_id, task_id)
    changes = data.model_dump(exclude_unset=True)
    for field in NOT_NULL_FIELDS & changes.keys():
        if changes[field] is None:
            raise HTTPException(422, f"{field} cannot be null")
    if "category_id" in changes:
        _ensure_category_owned(db, user_id, changes["category_id"])
    for field, value in changes.items():
        setattr(task, field, value)
    _apply_completion(task)
    db.commit()
    return task


def delete_task(db: Session, user_id: uuid.UUID, task_id: uuid.UUID) -> None:
    db.delete(get_task(db, user_id, task_id))
    db.commit()

