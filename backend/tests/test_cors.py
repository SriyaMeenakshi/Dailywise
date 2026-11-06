import pytest

ORIGIN = "http://localhost:3000"


@pytest.mark.parametrize("method", ["GET", "POST", "PUT", "PATCH", "DELETE"])
def test_browser_preflight_allows_every_method_the_api_uses(client, method):
    res = client.options(
        "/api/v1/tasks",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert res.status_code == 200, method
    assert res.headers["access-control-allow-origin"] == ORIGIN


def test_unlisted_origin_is_not_allowed(client):
    res = client.options(
        "/api/v1/tasks",
        headers={"Origin": "https://evil.example.com", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in res.headers
