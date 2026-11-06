from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.deps import get_current_user
from app.ai.errors import AIError
from app.api.routes import ai, categories, insights, plan, projects, task_details, tasks
from app.core.config import get_settings
from app.models import User
from app.schemas.user import UserRead


def create_app() -> FastAPI:
    settings = get_settings()
    if settings.is_production and (problems := settings.production_problems()):
        raise RuntimeError("Refusing to start in production: " + "; ".join(problems))
    app = FastAPI(
        title="Daywise API",
        version="1.0.0",
        # The interactive docs list every endpoint; keep them to development.
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    api = APIRouter(prefix="/api/v1")
    api.include_router(tasks.router)
    api.include_router(categories.router)
    api.include_router(projects.router)
    api.include_router(task_details.router)
    api.include_router(ai.router)
    api.include_router(plan.router)
    api.include_router(insights.router)

    @api.get("/me", response_model=UserRead, tags=["users"])
    def me(user: User = Depends(get_current_user)):
        return user

    app.include_router(api)

    @app.exception_handler(AIError)
    async def ai_error_handler(_request: Request, exc: AIError):
        # AI problems are reported cleanly and never affect the rest of the app.
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message, "code": exc.code})

    @app.get("/health", tags=["meta"])
    def health():
        return {"status": "ok"}

    return app


app = create_app()
