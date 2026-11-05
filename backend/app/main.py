from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.deps import get_current_user
from app.api.routes import categories, tasks
from app.core.config import get_settings
from app.models import User
from app.schemas.user import UserRead


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Daywise API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    api = APIRouter(prefix="/api/v1")
    api.include_router(tasks.router)
    api.include_router(categories.router)

    @api.get("/me", response_model=UserRead, tags=["users"])
    def me(user: User = Depends(get_current_user)):
        return user

    app.include_router(api)

    @app.get("/health", tags=["meta"])
    def health():
        return {"status": "ok"}

    return app


app = create_app()
