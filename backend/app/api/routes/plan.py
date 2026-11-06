import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.plan import (
    BlockRead,
    BlockUpdate,
    FixedBlockCreate,
    GenerateRequest,
    MoveRequest,
    PlannerPrefs,
    PlanRead,
)
from app.services import planner

router = APIRouter(tags=["planner"])
CurrentUser = Annotated[User, Depends(get_current_user)]
DB = Annotated[Session, Depends(get_db)]


def _one(db: DB, user: User, block) -> BlockRead:
    return planner._read(block, planner._levels(db, user.id, [block]))


@router.get("/plan", response_model=PlanRead)
def read_plan(user: CurrentUser, db: DB, date: date):
    return planner.get_plan(db, user.id, date)


@router.post("/plan/generate", response_model=PlanRead)
def generate_plan(body: GenerateRequest, user: CurrentUser, db: DB):
    """Deterministic: no AI involved. Re-run any time to recalculate the unlocked parts of the day."""
    return planner.generate(db, user.id, body)


@router.post("/plan/blocks", response_model=BlockRead, status_code=status.HTTP_201_CREATED)
def add_fixed_block(body: FixedBlockCreate, user: CurrentUser, db: DB):
    return _one(db, user, planner.create_fixed(db, user.id, body.date, body.title, body.start_min, body.end_min))


@router.patch("/plan/blocks/{block_id}", response_model=BlockRead)
def edit_block(block_id: uuid.UUID, body: BlockUpdate, user: CurrentUser, db: DB):
    changes = body.model_dump(exclude_unset=True)
    return _one(db, user, planner.update_block(db, user.id, block_id, changes))


@router.post("/plan/blocks/{block_id}/move", response_model=list[BlockRead])
def move(block_id: uuid.UUID, body: MoveRequest, user: CurrentUser, db: DB):
    return [_one(db, user, b) for b in planner.move_block(db, user.id, block_id, body.direction)]


@router.post("/plan/blocks/{block_id}/postpone", response_model=BlockRead)
def postpone(block_id: uuid.UUID, user: CurrentUser, db: DB):
    return _one(db, user, planner.postpone(db, user.id, block_id))


@router.delete("/plan/blocks/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_block(block_id: uuid.UUID, user: CurrentUser, db: DB):
    planner.delete_block(db, user.id, block_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/preferences/planner", response_model=PlannerPrefs)
def read_prefs(user: CurrentUser, db: DB):
    return planner.get_prefs(db, user.id)


@router.put("/preferences/planner", response_model=PlannerPrefs)
def write_prefs(body: PlannerPrefs, user: CurrentUser, db: DB):
    return planner.set_prefs(db, user.id, body)
