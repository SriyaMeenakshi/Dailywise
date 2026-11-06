import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Phase, Project, User
from app.schemas.project import (
    PhaseCreate,
    PhaseRead,
    PhaseUpdate,
    ProjectCreate,
    ProjectRead,
    ProjectUpdate,
)
from app.services import projects as service

router = APIRouter(tags=["projects"])
CurrentUser = Annotated[User, Depends(get_current_user)]
DB = Annotated[Session, Depends(get_db)]


@router.get("/projects", response_model=list[ProjectRead])
def list_projects(user: CurrentUser, db: DB, include_archived: bool = False):
    stmt = select(Project).where(Project.user_id == user.id).order_by(Project.created_at.desc())
    if not include_archived:
        stmt = stmt.where(Project.status != "archived")
    return service.build_read(db, user.id, list(db.scalars(stmt)), with_phases=False)


@router.post("/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(body: ProjectCreate, user: CurrentUser, db: DB):
    project = Project(user_id=user.id, **body.model_dump())
    db.add(project)
    db.commit()
    return service.build_read(db, user.id, [project], with_phases=True)[0]


@router.get("/projects/{project_id}", response_model=ProjectRead)
def get_project(project_id: uuid.UUID, user: CurrentUser, db: DB):
    project = service.get_project(db, user.id, project_id)
    return service.build_read(db, user.id, [project], with_phases=True)[0]


@router.patch("/projects/{project_id}", response_model=ProjectRead)
def update_project(project_id: uuid.UUID, body: ProjectUpdate, user: CurrentUser, db: DB):
    project = service.get_project(db, user.id, project_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        if value is None and field in {"name", "status"}:
            raise HTTPException(422, f"{field} cannot be null")
        setattr(project, field, value)
    db.commit()
    return service.build_read(db, user.id, [project], with_phases=True)[0]


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: uuid.UUID, user: CurrentUser, db: DB):
    """Deleting a project keeps its tasks; they simply become project-less."""
    db.delete(service.get_project(db, user.id, project_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/projects/{project_id}/phases", response_model=PhaseRead, status_code=status.HTTP_201_CREATED)
def create_phase(project_id: uuid.UUID, body: PhaseCreate, user: CurrentUser, db: DB):
    project = service.get_project(db, user.id, project_id)
    phase = Phase(
        user_id=user.id, project_id=project.id, name=body.name, sort_order=service.next_phase_order(db, project.id)
    )
    db.add(phase)
    db.commit()
    return phase


@router.patch("/phases/{phase_id}", response_model=PhaseRead)
def update_phase(phase_id: uuid.UUID, body: PhaseUpdate, user: CurrentUser, db: DB):
    phase = service.get_phase(db, user.id, phase_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(phase, field, value)
    db.commit()
    return phase


@router.delete("/phases/{phase_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_phase(phase_id: uuid.UUID, user: CurrentUser, db: DB):
    """Tasks in the phase stay in the project, unphased."""
    db.delete(service.get_phase(db, user.id, phase_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
