import time
import uuid

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.config import Settings, get_settings
from app.db.session import Base, get_db, make_engine
from app.main import create_app

JWT_SECRET = "test-secret-not-used-anywhere-real-0123456789"
SUPABASE_URL = "https://example.supabase.co"


def make_token(
    user_id: uuid.UUID | None = None,
    *,
    secret: str = JWT_SECRET,
    audience: str = "authenticated",
    issuer: str = f"{SUPABASE_URL}/auth/v1",
    expires_in: int = 3600,
    email: str | None = "student@example.com",
) -> str:
    claims = {
        "sub": str(user_id or uuid.uuid4()),
        "aud": audience,
        "iss": issuer,
        "exp": int(time.time()) + expires_in,
        "email": email,
        "user_metadata": {"full_name": "Test Student"},
    }
    return jwt.encode(claims, secret, algorithm="HS256")


@pytest.fixture
def client():
    engine = make_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: Settings(
        supabase_url=SUPABASE_URL, supabase_jwt_secret=JWT_SECRET
    )
    with TestClient(app) as c:
        yield c
    engine.dispose()


def auth(user_id: uuid.UUID | None = None, **kwargs) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(user_id, **kwargs)}"}


@pytest.fixture
def alice() -> dict[str, str]:
    return auth(uuid.UUID(int=1))


@pytest.fixture
def bob() -> dict[str, str]:
    return auth(uuid.UUID(int=2))
