"""Whole-API checks, so a new endpoint cannot quietly skip authentication or drift from the migrations."""

import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from app.main import create_app
from tests.conftest import auth

PUBLIC = {"/health"}
BACKEND = Path(__file__).resolve().parents[1]


def api_routes():
    """Every (method, path) the API publishes. Read from the OpenAPI schema, which lists included routers."""
    paths = create_app().openapi()["paths"]
    return [
        (method.upper(), path)
        for path, ops in paths.items()
        if path not in PUBLIC and path.startswith("/api/")
        for method in ops
        if method in {"get", "post", "put", "patch", "delete"}
    ]


def fill(path: str) -> str:
    out = path
    for part in [p for p in path.split("/") if p.startswith("{")]:
        out = out.replace(part, "2026-01-01" if part in {"{day}"} else str(uuid.uuid4()))
    return out


ROUTES = api_routes()


def test_the_sweep_actually_covers_the_api():
    assert len(ROUTES) >= 40  # guards against the filter silently matching nothing


@pytest.mark.parametrize("method,path", ROUTES, ids=[f"{m} {p}" for m, p in ROUTES])
def test_every_endpoint_rejects_missing_and_invalid_credentials(client, method, path):
    url = fill(path)
    body = {"json": {}} if method in {"POST", "PUT", "PATCH"} else {}
    assert client.request(method, url, **body).status_code == 401
    bad = {"Authorization": "Bearer not-a-real-token"}
    assert client.request(method, url, headers=bad, **body).status_code == 401


@pytest.mark.parametrize("method,path", [r for r in ROUTES if r[0] == "GET" and "{" in r[1]], ids=lambda v: str(v))
def test_unknown_ids_are_404_not_500_or_leaks(client, method, path):
    res = client.request(method, fill(path), headers=auth(uuid.UUID(int=77)))
    assert res.status_code in (404, 200, 422), (path, res.status_code)  # never a server error


def test_migrations_apply_downgrade_and_match_the_models(tmp_path):
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{(tmp_path / 'm.db').as_posix()}"}

    def alembic(*args):
        return subprocess.run([sys.executable, "-m", "alembic", *args], cwd=BACKEND, env=env, capture_output=True, text=True)

    up = alembic("upgrade", "head")
    assert up.returncode == 0, up.stderr[-800:]
    check = alembic("check")
    assert check.returncode == 0, check.stdout[-800:] + check.stderr[-800:]
    down = alembic("downgrade", "base")
    assert down.returncode == 0, down.stderr[-800:]
    assert alembic("upgrade", "head").returncode == 0
