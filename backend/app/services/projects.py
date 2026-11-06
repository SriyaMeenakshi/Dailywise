import uuid
from collections import defaultdict

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Phase, Project, Subtask, Task
from app.schemas.project import PhaseRead, ProgressRead, ProjectRead
from app.services.progress import Progress, SubtaskInfo, TaskInfo, compute_progress


def get_project(db: Session, user_id: uuid.UUID, project_id: uuid.UUID) -> Project:
    project = db.scalar(select(Project).where(Project.id == project_id, Project.user_id == user_id))
    if project is None:
        raise HTTPException(404, "Project not found")
    return project


def get_phase(db: Session, user_id: uuid.UUID, phase_id: uuid.UUID) -> Phase:
    phase = db.scalar(select(Phase).where(Phase.id == phase_id, Phase.user_id == user_id))
    if phase is None:
        raise HTTPException(404, "Phase not found")
    return phase


def _read(p: Progress) -> ProgressRead:
    return ProgressRead(**p.__dict__)


def build_read(db: Session, user_id: uuid.UUID, projects: list[Project], *, with_phases: bool) -> list[ProjectRead]:
    """Attach effort-weighted progress (overall and per phase) to each project."""
    ids = [p.id for p in projects]
    tasks = list(db.scalars(select(Task).where(Task.user_id == user_id, Task.project_id.in_(ids)))) if ids else []
    subtasks: dict[uuid.UUID, list[SubtaskInfo]] = defaultdict(list)
    if tasks:
        rows = db.scalars(select(Subtask).where(Subtask.task_id.in_([t.id for t in tasks])))
        for s in rows:
            subtasks[s.task_id].append(SubtaskInfo(s.done, s.estimated_minutes))

    by_project: dict[uuid.UUID, list[Task]] = defaultdict(list)
    for t in tasks:
        by_project[t.project_id].append(t)
    info = lambda t: TaskInfo(t.status, t.estimated_minutes, subtasks[t.id])  # noqa: E731

    phases_by_project: dict[uuid.UUID, list[Phase]] = defaultdict(list)
    if with_phases and ids:
        for ph in db.scalars(
            select(Phase).where(Phase.project_id.in_(ids)).order_by(Phase.sort_order, Phase.created_at)
        ):
            phases_by_project[ph.project_id].append(ph)

    result = []
    for project in projects:
        own = by_project[project.id]
        read = ProjectRead.model_validate(project)
        read.progress = _read(compute_progress([info(t) for t in own]))
        if with_phases:
            for ph in phases_by_project[project.id]:
                in_phase = [t for t in own if t.phase_id == ph.id]
                deadlines = [t.deadline for t in in_phase if t.deadline]
                phase = PhaseRead.model_validate(ph)
                phase.progress = _read(compute_progress([info(t) for t in in_phase]))
                phase.earliest_deadline = min(deadlines) if deadlines else None
                phase.latest_deadline = max(deadlines) if deadlines else None
                read.phases.append(phase)
            loose = [t for t in own if t.phase_id is None]
            read.unphased_progress = _read(compute_progress([info(t) for t in loose]))
        result.append(read)
    return result


def next_phase_order(db: Session, project_id: uuid.UUID) -> int:
    return (db.scalar(select(func.max(Phase.sort_order)).where(Phase.project_id == project_id)) or 0) + 1
