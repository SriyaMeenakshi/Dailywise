import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import update
from sqlalchemy.orm import sessionmaker

from app.models import Task
from app.services import insights

T = "/api/v1/tasks"
A = "/api/v1/analytics"
R = "/api/v1/reviews"
ALICE_ID = uuid.UUID(int=1)


def task(client, h, title="t", **kw):
    res = client.post(T, json={"title": title, "status": "not_started", **kw}, headers=h)
    assert res.status_code == 201, res.text
    return res.json()


def complete(client, h, title="t", **kw):
    t = task(client, h, title, **kw)
    client.patch(f"{T}/{t['id']}", json={"status": "completed"}, headers=h)
    return t


def set_completed_at(engine, task_id, when: datetime):
    with sessionmaker(bind=engine)() as s:
        s.execute(update(Task).where(Task.id == uuid.UUID(task_id)).values(completed_at=when))
        s.commit()


def provision(client, h):
    client.get("/api/v1/me", headers=h)


def today_str(offset=0):
    return (datetime.now(UTC) + timedelta(minutes=offset)).date().isoformat()


# ── analytics ───────────────────────────────────────────────────────────────────
def test_empty_account_has_zeros_and_no_invented_data(client, alice):
    body = client.get(A, headers=alice).json()
    assert (body["completed"], body["pending"], body["overdue"], body["blocked"]) == (0, 0, 0, 0)
    assert len(body["daily"]) == 7 and all(d["completed"] == 0 for d in body["daily"])
    assert body["by_category"] == [] and body["projects"] == [] and body["time_accuracy"]["tasks"] == 0


def test_counts_completed_pending_overdue_blocked(client, alice):
    complete(client, alice, "done")
    task(client, alice, "open")
    task(client, alice, "late", deadline="2020-01-01T00:00:00Z")
    task(client, alice, "stuck", status="blocked")
    task(client, alice, "gone", status="archived")
    body = client.get(A, headers=alice).json()
    assert (body["completed"], body["pending"], body["overdue"], body["blocked"]) == (1, 3, 1, 1)
    assert body["daily"][-1]["completed"] == 1 and body["daily"][-1]["date"] == today_str()


def test_window_length_follows_days_and_excludes_older_completions(client, alice, engine):
    old = complete(client, alice, "old")
    set_completed_at(engine, old["id"], datetime.now(UTC) - timedelta(days=20))
    complete(client, alice, "recent")
    assert client.get(A, params={"days": 7}, headers=alice).json()["completed"] == 1
    month = client.get(A, params={"days": 30}, headers=alice).json()
    assert month["completed"] == 2 and len(month["daily"]) == 30


def test_days_parameter_is_validated(client, alice):
    for bad in (0, 91, -1):
        assert client.get(A, params={"days": bad}, headers=alice).status_code == 422
    assert client.get(A, params={"utc_offset_minutes": 9999}, headers=alice).status_code == 422


def test_completions_land_on_the_users_local_day(client, alice, db):
    provision(client, alice)
    t = complete(client, alice, "late night")
    now = datetime(2026, 11, 10, 20, 0, tzinfo=UTC)  # 01:30 on Nov 11 in UTC+5:30
    db.execute(update(Task).where(Task.id == uuid.UUID(t["id"])).values(completed_at=datetime(2026, 11, 10, 19, 0, tzinfo=UTC)))
    db.commit()
    ist = insights.analytics(db, ALICE_ID, 3, 330, now=now)
    utc = insights.analytics(db, ALICE_ID, 3, 0, now=now)
    assert {d.date.isoformat(): d.completed for d in ist.daily}["2026-11-11"] == 1
    assert {d.date.isoformat(): d.completed for d in utc.daily}["2026-11-10"] == 1
    assert ist.daily[-1].date == date(2026, 11, 11) and utc.daily[-1].date == date(2026, 11, 10)


def test_completed_minutes_prefer_actual_over_estimate(client, alice):
    complete(client, alice, "a", estimated_minutes=60, actual_minutes=45)
    complete(client, alice, "b", estimated_minutes=30)
    assert client.get(A, headers=alice).json()["daily"][-1]["completed_minutes"] == 75


def test_on_time_rate_uses_real_deadlines(client, alice):
    complete(client, alice, "early", deadline="2099-01-01T00:00:00Z")
    complete(client, alice, "late", deadline="2020-01-01T00:00:00Z")
    complete(client, alice, "no deadline")
    body = client.get(A, headers=alice).json()
    assert (body["completed"], body["completed_with_deadline"], body["completed_on_time"]) == (3, 2, 1)


def test_category_progress_includes_uncategorised_and_hides_empty(client, alice):
    cats = client.get("/api/v1/categories", headers=alice).json()
    academic = next(c for c in cats if c["name"] == "Academic")
    complete(client, alice, "a1", category_id=academic["id"])
    task(client, alice, "a2", category_id=academic["id"])
    task(client, alice, "loose")
    rows = {r["name"]: r for r in client.get(A, headers=alice).json()["by_category"]}
    assert set(rows) == {"Academic", "Uncategorised"}
    assert (rows["Academic"]["completed"], rows["Academic"]["pending"]) == (1, 1)
    assert (rows["Uncategorised"]["completed"], rows["Uncategorised"]["pending"]) == (0, 1)


def test_time_accuracy_only_counts_tasks_with_both_numbers(client, alice):
    complete(client, alice, "over", estimated_minutes=60, actual_minutes=120)
    complete(client, alice, "under", estimated_minutes=60, actual_minutes=50)
    complete(client, alice, "no actual", estimated_minutes=60)
    complete(client, alice, "no estimate", actual_minutes=10)
    acc = client.get(A, headers=alice).json()["time_accuracy"]
    assert (acc["tasks"], acc["estimated_minutes"], acc["actual_minutes"]) == (2, 120, 170)
    assert acc["biggest_misses"][0]["title"] == "over"


def test_project_completion_is_effort_weighted(client, alice):
    p = client.post("/api/v1/projects", json={"name": "P"}, headers=alice).json()
    complete(client, alice, "small", project_id=p["id"], estimated_minutes=30)
    task(client, alice, "big", project_id=p["id"], estimated_minutes=270)
    done = client.post("/api/v1/projects", json={"name": "Archived", "status": "archived"}, headers=alice).json()
    rows = client.get(A, headers=alice).json()["projects"]
    assert [r["name"] for r in rows] == ["P"] and rows[0]["percent"] == 10.0 and done


def test_analytics_are_private_to_each_user(client, alice, bob):
    complete(client, alice, "mine")
    body = client.get(A, headers=bob).json()
    assert body["completed"] == 0 and body["pending"] == 0


# ── daily reflection ────────────────────────────────────────────────────────────
def test_review_facts_come_from_real_tasks(client, alice):
    complete(client, alice, "finished", estimated_minutes=40)
    task(client, alice, "due today", deadline=f"{today_str()}T00:30:00Z")
    task(client, alice, "stuck", status="blocked")
    task(client, alice, "later", importance=5, urgency=5, impact=5)
    facts = client.get(f"{R}/{today_str()}", headers=alice).json()["facts"]
    assert [t["title"] for t in facts["completed"]] == ["finished"] and facts["completed_minutes"] == 40
    assert "due today" in [t["title"] for t in facts["remaining"]]
    assert [t["title"] for t in facts["blocked"]] == ["stuck"]
    tomorrow = [t["title"] for t in facts["suggested_tomorrow"]]
    assert tomorrow[0] == "later" and "stuck" not in tomorrow and "finished" not in tomorrow


def test_review_for_a_quiet_day_is_empty_not_fabricated(client, alice):
    res = client.get(f"{R}/2020-05-05", headers=alice).json()
    assert res["saved"] is None and res["facts"]["completed"] == [] and res["facts"]["completed_minutes"] == 0


def test_review_text_saves_updates_and_clears(client, alice):
    day = today_str()
    body = {"accomplished": "  Shipped the API ", "remaining": "UI", "blockers": "", "tomorrow_focus": "Tests"}
    saved = client.put(f"{R}/{day}", json=body, headers=alice).json()["saved"]
    assert saved == {"accomplished": "Shipped the API", "remaining": "UI", "blockers": "", "tomorrow_focus": "Tests"}
    client.put(f"{R}/{day}", json={**body, "blockers": "Waiting on review"}, headers=alice)
    again = client.get(f"{R}/{day}", headers=alice).json()["saved"]
    assert again["blockers"] == "Waiting on review" and again["accomplished"] == "Shipped the API"
    cleared = client.put(f"{R}/{day}", json={}, headers=alice).json()["saved"]
    assert set(cleared.values()) == {""}


def test_review_validation(client, alice):
    assert client.put(f"{R}/{today_str()}", json={"accomplished": "x" * 5001}, headers=alice).status_code == 422
    assert client.get(f"{R}/not-a-date", headers=alice).status_code == 422


def test_reviews_are_private_and_per_day(client, alice, bob):
    client.put(f"{R}/{today_str()}", json={"accomplished": "secret"}, headers=alice)
    assert client.get(f"{R}/{today_str()}", headers=bob).json()["saved"] is None
    assert client.get(f"{R}/2020-01-01", headers=alice).json()["saved"] is None


def test_review_completed_list_respects_timezone(client, alice, engine):
    t = complete(client, alice, "edge")
    set_completed_at(engine, t["id"], datetime(2026, 11, 10, 19, 0, tzinfo=UTC))
    assert [x["title"] for x in client.get(f"{R}/2026-11-11", params={"utc_offset_minutes": 330}, headers=alice).json()["facts"]["completed"]] == ["edge"]
    assert client.get(f"{R}/2026-11-11", params={"utc_offset_minutes": 0}, headers=alice).json()["facts"]["completed"] == []
    assert [x["title"] for x in client.get(f"{R}/2026-11-10", params={"utc_offset_minutes": 0}, headers=alice).json()["facts"]["completed"]] == ["edge"]


@pytest.mark.parametrize("path", [f"{A}", f"{R}/2026-01-01"])
def test_insights_require_authentication(client, path):
    assert client.get(path).status_code == 401
