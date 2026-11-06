from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.ai import usage_tracker
from app.ai.ai_gateway import AIGateway
from app.ai.deps import get_gateway
from app.ai.model_router import model_for
from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models import User
from app.schemas.ai import (
    AIStatus,
    ApplyRequest,
    ApplyResponse,
    DecomposeRequest,
    DecomposeResponse,
    ParseRequest,
    ParseResponse,
)
from app.services import ai_tasks

router = APIRouter(prefix="/ai", tags=["ai"])
CurrentUser = Annotated[User, Depends(get_current_user)]
DB = Annotated[Session, Depends(get_db)]
Gateway = Annotated[AIGateway, Depends(get_gateway)]


@router.get("/status", response_model=AIStatus)
def status(user: CurrentUser, db: DB, settings: Annotated[Settings, Depends(get_settings)]):
    """Is AI available, and how much of today's allowance is left? Never calls the provider."""
    usage = usage_tracker.usage_today(db, user.id, settings)
    return AIStatus(
        configured=settings.ai_configured,
        model=model_for("parse_tasks", settings) if settings.ai_configured else None,
        complex_model=model_for("decompose_project", settings) if settings.ai_configured else None,
        requests_today=usage.requests_today,
        request_limit=usage.request_limit,
        tokens_today=usage.tokens_today,
        token_limit=usage.token_limit,
        cost_today_usd=round(usage.cost_today_usd, 6),
        cached_today=usage.cached_today,
        cost_tracking=bool(settings.ai_price_input_per_mtok or settings.ai_price_output_per_mtok),
    )


@router.post("/parse-tasks", response_model=ParseResponse)
def parse_tasks(body: ParseRequest, user: CurrentUser, db: DB, gateway: Gateway):
    """Suggest tasks from free text. Saves nothing: the user reviews the result first."""
    return ai_tasks.parse_tasks(db, user.id, gateway, body)


@router.post("/decompose-project", response_model=DecomposeResponse)
def decompose_project(body: DecomposeRequest, user: CurrentUser, db: DB, gateway: Gateway):
    """Suggest phases, tasks, subtasks and dependencies for a goal. Saves nothing."""
    return ai_tasks.decompose_project(db, user.id, gateway, body)


@router.post("/decompose-project/apply", response_model=ApplyResponse, status_code=201)
def apply_breakdown(body: ApplyRequest, user: CurrentUser, db: DB):
    """Create the plan the user approved. Does not call the AI."""
    return ai_tasks.apply_plan(db, user.id, body)
