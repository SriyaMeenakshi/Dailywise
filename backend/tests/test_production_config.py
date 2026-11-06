import pytest

from app.core import config
from app.main import create_app

GOOD = dict(
    app_env="production",
    database_url="postgresql+psycopg://u:p@db.example.com/postgres",
    supabase_url="https://abc.supabase.co",
    allowed_origins="https://daywise.example.com",
)


def settings(**kw):
    return config.Settings(**{**GOOD, **kw})


def test_a_correct_production_config_has_no_problems():
    assert settings().production_problems() == []


@pytest.mark.parametrize(
    "override,fragment",
    [
        ({"database_url": "sqlite:///./x.db"}, "PostgreSQL"),
        ({"supabase_url": ""}, "SUPABASE_URL"),
        ({"allowed_origins": "*"}, "ALLOWED_ORIGINS"),
        ({"allowed_origins": "http://localhost:3000"}, "ALLOWED_ORIGINS"),
        ({"allowed_origins": ""}, "ALLOWED_ORIGINS"),
        ({"allowed_origins": "https://ok.example.com,http://localhost:3000"}, "ALLOWED_ORIGINS"),
    ],
)
def test_unsafe_production_settings_are_reported(override, fragment):
    assert any(fragment in p for p in settings(**override).production_problems())


def test_production_refuses_to_start_when_misconfigured(monkeypatch):
    monkeypatch.setattr("app.main.get_settings", lambda: settings(database_url="sqlite:///x.db"))
    with pytest.raises(RuntimeError, match="Refusing to start in production"):
        create_app()


def test_production_hides_api_docs_and_development_exposes_them(monkeypatch):
    monkeypatch.setattr("app.main.get_settings", lambda: settings())
    prod = create_app()
    assert prod.docs_url is None and prod.openapi_url is None
    monkeypatch.setattr("app.main.get_settings", lambda: config.Settings(app_env="development"))
    assert create_app().docs_url == "/docs"
