from datetime import date as Date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.insights import Analytics, ReviewRead, ReviewText
from app.services import insights

router = APIRouter(tags=["insights"])
CurrentUser = Annotated[User, Depends(get_current_user)]
DB = Annotated[Session, Depends(get_db)]
Offset = Annotated[int, Query(ge=-840, le=840, description="Minutes the user's clock is ahead of UTC")]


@router.get("/reviews/{day}", response_model=ReviewRead)
def read_review(day: Date, user: CurrentUser, db: DB, utc_offset_minutes: Offset = 0):
    return insights.get_review(db, user.id, day, utc_offset_minutes)


@router.put("/reviews/{day}", response_model=ReviewRead)
def write_review(day: Date, body: ReviewText, user: CurrentUser, db: DB, utc_offset_minutes: Offset = 0):
    insights.save_review(db, user.id, day, body)
    return insights.get_review(db, user.id, day, utc_offset_minutes)


@router.get("/analytics", response_model=Analytics)
def read_analytics(user: CurrentUser, db: DB, days: Annotated[int, Query(ge=1, le=90)] = 7, utc_offset_minutes: Offset = 0):
    return insights.analytics(db, user.id, days, utc_offset_minutes)
