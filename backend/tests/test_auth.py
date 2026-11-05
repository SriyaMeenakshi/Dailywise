import jwt
import pytest

from tests.conftest import auth, make_token

URL = "/api/v1/me"


def test_health_is_public(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_missing_token_rejected(client):
    assert client.get(URL).status_code == 401


@pytest.mark.parametrize(
    "kwargs",
    [
        {"secret": "wrong-secret-wrong-secret-wrong-secret"},
        {"audience": "anon"},
        {"issuer": "https://evil.example.com/auth/v1"},
        {"expires_in": -10},
    ],
    ids=["bad-signature", "bad-audience", "bad-issuer", "expired"],
)
def test_invalid_tokens_rejected(client, kwargs):
    assert client.get(URL, headers=auth(**kwargs)).status_code == 401


def test_garbage_and_unsigned_tokens_rejected(client):
    assert client.get(URL, headers={"Authorization": "Bearer not-a-jwt"}).status_code == 401
    unsigned = jwt.encode({"sub": "x", "aud": "authenticated"}, key=None, algorithm="none")
    assert client.get(URL, headers={"Authorization": f"Bearer {unsigned}"}).status_code == 401


def test_valid_token_provisions_user_with_default_categories(client, alice):
    me = client.get(URL, headers=alice)
    assert me.status_code == 200
    assert me.json()["email"] == "student@example.com"
    names = [c["name"] for c in client.get("/api/v1/categories", headers=alice).json()]
    assert names[0] == "Academic" and "Health and fitness" in names and len(names) == 9


def test_provisioning_is_idempotent(client, alice):
    client.get(URL, headers=alice)
    client.get(URL, headers=alice)
    assert len(client.get("/api/v1/categories", headers=alice).json()) == 9


def test_make_token_helper_produces_decodable_token():
    assert jwt.decode(make_token(), options={"verify_signature": False})["aud"] == "authenticated"
