import threading
import uuid

import pytest
from pydantic import BaseModel

from app.ai import ai_gateway, usage_tracker
from app.ai.ai_gateway import AIGateway
from app.ai.errors import (
    AIBusy,
    AIInputTooLong,
    AIInvalidResponse,
    AINotConfigured,
    AIProviderError,
    AIQuotaExceeded,
    AIRateLimited,
    AITimeout,
    ProviderError,
    ProviderRetryable,
)
from app.ai.providers.base import ProviderResponse
from app.models import AICache, AIUsageLog, User
from tests.conftest import FakeProvider, make_settings

U1, U2 = uuid.UUID(int=11), uuid.UUID(int=12)
GOOD = {"tasks": [{"title": "Do the thing"}], "questions": []}


class Out(BaseModel):
    tasks: list[dict]
    questions: list[str] = []


@pytest.fixture(autouse=True)
def users(db):
    db.add_all([User(id=U1, email="a@x.com"), User(id=U2, email="b@x.com")])
    db.commit()


def gw(provider, sleeps=None, **settings):
    return AIGateway(make_settings(**settings), provider, sleep=(sleeps.append if sleeps is not None else lambda s: None))


def run(gateway, db, user=U1, text="hello", payload=None, **kw):
    return gateway.run(
        db, user, feature="parse_tasks", input_text=text, user_message=text,
        cache_payload=payload or {"text": text}, schema=Out, **kw,
    )


def logs(db):
    return db.query(AIUsageLog).order_by(AIUsageLog.created_at).all()


def test_success_validates_logs_usage_and_cost(db):
    provider = FakeProvider(GOOD)
    result = run(gw(provider), db)
    assert result.data.tasks == [{"title": "Do the thing"}] and result.cached is False
    (log,) = logs(db)
    assert (log.feature, log.model, log.prompt_version, log.status) == ("parse_tasks", "test-model", "1.0", "ok")
    assert (log.input_tokens, log.output_tokens, log.attempts) == (100, 50, 1)
    assert log.cost_usd == pytest.approx((100 * 1.0 + 50 * 2.0) / 1e6)


def test_second_identical_request_is_served_from_cache_without_a_call(db):
    provider = FakeProvider(GOOD)
    g = gw(provider)
    run(g, db)
    again = run(g, db)
    assert again.cached is True and len(provider.calls) == 1
    assert [l.status for l in logs(db)] == ["ok", "cached"]
    assert usage_tracker.usage_today(db, U1, g.settings).requests_today == 1  # cache hits are free


def test_cache_is_per_user(db):
    provider = FakeProvider(GOOD)
    g = gw(provider)
    run(g, db, user=U1)
    assert run(g, db, user=U2).cached is False and len(provider.calls) == 2


def test_cache_key_changes_with_payload_and_force_bypasses_cache(db):
    provider = FakeProvider(GOOD)
    g = gw(provider)
    run(g, db, payload={"text": "x", "today": "2026-11-06"})
    assert run(g, db, payload={"text": "x", "today": "2026-11-07"}).cached is False
    assert run(g, db, payload={"text": "x", "today": "2026-11-07"}, force=True).cached is False
    assert len(provider.calls) == 3


def test_cached_answer_still_served_when_ai_is_not_configured(db):
    run(gw(FakeProvider(GOOD)), db)
    offline = AIGateway(make_settings(gemini_api_key=""), None)
    assert run(offline, db).cached is True


def test_missing_credentials_raise_not_configured_and_make_no_call(db):
    with pytest.raises(AINotConfigured):
        run(AIGateway(make_settings(gemini_api_key=""), None), db)
    with pytest.raises(AINotConfigured):
        run(AIGateway(make_settings(), None), db)
    assert logs(db) == []


def test_input_too_long_rejected_before_anything_else(db):
    provider = FakeProvider(GOOD)
    with pytest.raises(AIInputTooLong):
        run(gw(provider, ai_max_input_chars=10), db, text="x" * 11)
    assert provider.calls == []


def test_request_quota_enforced_per_user(db):
    provider = FakeProvider(GOOD)
    g = gw(provider, ai_daily_request_limit=2)
    run(g, db, text="a")
    run(g, db, text="b")
    with pytest.raises(AIQuotaExceeded):
        run(g, db, text="c")
    assert len(provider.calls) == 2
    assert run(g, db, user=U2, text="c").cached is False  # other users are unaffected
    assert run(g, db, text="a").cached is True  # cached answers still work at the limit


def test_token_quota_enforced(db):
    g = gw(FakeProvider(GOOD), ai_daily_token_limit=150)
    run(g, db, text="a")  # uses 150 tokens
    with pytest.raises(AIQuotaExceeded):
        run(g, db, text="b")


def test_invalid_json_is_retried_then_succeeds(db):
    provider = FakeProvider("not json {", GOOD)
    result = run(gw(provider), db)
    assert result.cached is False and len(provider.calls) == 2
    (log,) = logs(db)
    assert log.attempts == 2 and log.input_tokens == 200  # tokens from both attempts are counted


@pytest.mark.parametrize("bad", ["", "   ", "```json\n{\"nope\": 1}\n```", '{"tasks": "wrong type"}', "[1,2]"])
def test_persistently_bad_output_fails_cleanly_and_is_not_cached(db, bad):
    provider = FakeProvider(bad)
    with pytest.raises(AIInvalidResponse):
        run(gw(provider), db)
    assert len(provider.calls) == 3 and db.query(AICache).count() == 0
    (log,) = logs(db)
    assert log.status == "error" and log.error_code == "invalid_response"


def test_markdown_fenced_json_is_accepted(db):
    fenced = "```json\n" + '{"tasks": [{"title": "x"}]}' + "\n```"
    assert run(gw(FakeProvider(fenced)), db).data.tasks[0]["title"] == "x"


def test_rate_limit_retries_with_exponential_backoff(db):
    limited = ProviderRetryable("slow down", kind="rate_limited")
    sleeps = []
    provider = FakeProvider(limited, limited, GOOD)
    run(gw(provider, sleeps, ai_max_retries=2, ai_retry_base_seconds=1.0), db)
    assert sleeps == [1.0, 2.0] and len(provider.calls) == 3


def test_retry_after_header_is_honoured_and_capped(db):
    sleeps = []
    provider = FakeProvider(
        ProviderRetryable("x", kind="rate_limited", retry_after=5), ProviderRetryable("x", kind="rate_limited", retry_after=999), GOOD
    )
    run(gw(provider, sleeps), db)
    assert sleeps == [5, 30.0]


@pytest.mark.parametrize(
    "kind,error",
    [("rate_limited", AIRateLimited), ("timeout", AITimeout), ("unavailable", AIProviderError)],
)
def test_retries_exhausted_map_to_specific_errors(db, kind, error):
    provider = FakeProvider(ProviderRetryable("boom", kind=kind))
    with pytest.raises(error):
        run(gw(provider, ai_max_retries=2), db)
    assert len(provider.calls) == 3
    (log,) = logs(db)
    assert log.status == "error" and log.attempts == 3


def test_non_retryable_provider_error_is_not_retried(db):
    provider = FakeProvider(ProviderError("bad key"))
    with pytest.raises(AIProviderError):
        run(gw(provider), db)
    assert len(provider.calls) == 1


def test_empty_candidates_response_counts_as_invalid(db):
    provider = FakeProvider(ProviderResponse(text="", input_tokens=10, output_tokens=0))
    with pytest.raises(AIInvalidResponse):
        run(gw(provider), db)


def test_duplicate_in_flight_request_is_rejected(db):
    started, release = threading.Event(), threading.Event()

    class Slow(FakeProvider):
        def generate(self, request):
            started.set()
            release.wait(5)
            return super().generate(request)

    provider = Slow(GOOD)
    g = gw(provider)
    first: dict = {}
    t = threading.Thread(target=lambda: first.setdefault("r", run(g, _fresh_session(db))))
    t.start()
    assert started.wait(5)
    try:
        with pytest.raises(AIBusy):
            run(g, db)
    finally:
        release.set()
        t.join(5)
    assert first["r"].cached is False and len(provider.calls) == 1
    assert ai_gateway._inflight == set()  # released afterwards


def _fresh_session(db):
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(bind=db.get_bind(), expire_on_commit=False)()


def test_inflight_slot_is_released_after_failure(db):
    with pytest.raises(AIInvalidResponse):
        run(gw(FakeProvider("nope")), db)
    assert ai_gateway._inflight == set()


def test_model_router_uses_stronger_model_for_complex_features(db):
    provider = FakeProvider({"project_name": "P", "objective": "O", "phases": []})
    from app.ai.model_router import model_for

    s = make_settings(ai_model="cheap", ai_model_complex="strong")
    assert model_for("parse_tasks", s) == "cheap" and model_for("decompose_project", s) == "strong"
    assert model_for("decompose_project", make_settings(ai_model="cheap")) == "cheap"
    assert provider.calls == []


def test_usage_summary(db):
    g = gw(FakeProvider(GOOD), ai_daily_request_limit=5)
    run(g, db, text="a")
    run(g, db, text="a")
    u = usage_tracker.usage_today(db, U1, g.settings)
    assert (u.requests_today, u.cached_today, u.tokens_today, u.requests_left) == (1, 1, 150, 4)
    assert u.cost_today_usd > 0

