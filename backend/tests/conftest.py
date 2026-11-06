import time
import uuid

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.ai.ai_gateway import AIGateway
from app.ai.deps import get_gateway
from app.ai.providers.base import ProviderResponse
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


def make_settings(**overrides) -> Settings:
    base = dict(
        supabase_url=SUPABASE_URL,
        supabase_jwt_secret=JWT_SECRET,
        gemini_api_key="test-key",
        ai_model="test-model",
        ai_retry_base_seconds=1.0,
        ai_price_input_per_mtok=1.0,  # fake round numbers so cost maths is checkable
        ai_price_output_per_mtok=2.0,
    )
    return Settings(**{**base, **overrides})


class FakeProvider:
    """Scripted provider. Each item is a ProviderResponse, a JSON-able dict/str, or an exception."""

    def __init__(self, *script):
        self.script = list(script)
        self.calls = []

    def generate(self, request):
        self.calls.append(request)
        item = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if isinstance(item, Exception):
            raise item
        if isinstance(item, ProviderResponse):
            return item
        import json

        text = item if isinstance(item, str) else json.dumps(item)
        return ProviderResponse(text=text, input_tokens=100, output_tokens=50)


@pytest.fixture
def engine():
    engine = make_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine):
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with Session() as session:
        yield session


@pytest.fixture
def make_client(engine):
    """Factory so a test can choose its AI provider script and settings."""
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    clients = []

    def factory(provider=None, **settings_overrides):
        settings = make_settings(**settings_overrides)

        def override_db():
            session = Session()
            try:
                yield session
            finally:
                session.close()

        app = create_app()
        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_settings] = lambda: settings
        app.dependency_overrides[get_gateway] = lambda: AIGateway(settings, provider, sleep=lambda _s: None)
        client = TestClient(app)
        client.__enter__()
        clients.append(client)
        return client

    yield factory
    for c in clients:
        c.__exit__(None, None, None)


@pytest.fixture
def client(make_client):
    return make_client()


def auth(user_id: uuid.UUID | None = None, **kwargs) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(user_id, **kwargs)}"}


@pytest.fixture
def alice() -> dict[str, str]:
    return auth(uuid.UUID(int=1))


@pytest.fixture
def bob() -> dict[str, str]:
    return auth(uuid.UUID(int=2))

