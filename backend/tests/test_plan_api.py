import pytest

T = "/api/v1/tasks"
GEN = "/api/v1/plan/generate"
PLAN = "/api/v1/plan"
BLOCKS = "/api/v1/plan/blocks"
DAY = "2099-03-10"
H = 60


def task(client, h, title="t", minutes=60, **kw):
    res = client.post(T, json={"title": title, "estimated_minutes": minutes, "status": "not_started", **kw}, headers=h)
    assert res.status_code == 201, res.text
    return res.json()


def generate(client, h, **kw):
    res = client.post(GEN, json={"date": DAY, **kw}, headers=h)
    assert res.status_code == 200, res.text
    return res.json()


def task_blocks(plan):
    return [b for b in plan["blocks"] if b["kind"] == "task"]


def test_generate_builds_a_realistic_day_from_priorities(client, alice):
    task(client, alice, "low", importance=1, urgency=1, impact=1)
    task(client, alice, "high", importance=5, urgency=5, impact=5)
    plan = generate(client, alice)
    assert [b["title"] for b in task_blocks(plan)] == ["high", "low"]
    assert plan["window_start"] == 540 and plan["window_end"] == 1020 and plan["break_minutes"] == 10
    assert plan["planned_minutes"] == 120 and plan["free_minutes"] == 480 - 120 - 10
    assert [b["kind"] for b in plan["blocks"]] == ["task", "break", "task"]


def test_nothing_is_scheduled_beyond_availability(client, alice):
    for i in range(15):
        task(client, alice, f"t{i}", 90)
    plan = generate(client, alice)
    assert all(540 <= b["start_min"] and b["end_min"] <= 1020 for b in plan["blocks"])
    assert plan["unscheduled_total"] > 0 and len(plan["unscheduled"]) <= 8
    assert all(u["reason"] for u in plan["unscheduled"])


def test_blocked_and_finished_tasks_are_not_planned(client, alice):
    task(client, alice, "ok")
    task(client, alice, "blocked", status="blocked")
    task(client, alice, "done", status="completed")
    task(client, alice, "old", status="archived")
    assert [b["title"] for b in task_blocks(generate(client, alice))] == ["ok"]


def test_dependencies_are_respected_in_the_plan(client, alice):
    base = task(client, alice, "base", importance=1, urgency=1, impact=1)
    child = task(client, alice, "child", importance=5, urgency=5, impact=5)
    client.post(f"{T}/{child['id']}/dependencies", json={"depends_on_id": base["id"]}, headers=alice)
    assert [b["title"] for b in task_blocks(generate(client, alice))] == ["base", "child"]


def test_deadline_warning_uses_the_users_timezone(client, alice):
    # Deadline 10:00 local on the plan day in UTC+5:30 = 04:30 UTC. A 60-minute task starting 9:00 ends 10:00.
    task(client, alice, "a", 120, deadline=f"{DAY}T04:30:00Z")
    block = task_blocks(generate(client, alice, utc_offset_minutes=330))[0]
    assert block["warning"] == "Finishes after its deadline"
    task(client, alice, "b", 30, deadline="2099-03-12T04:30:00Z")
    blocks = {b["title"]: b for b in task_blocks(generate(client, alice, utc_offset_minutes=330))}
    assert blocks["b"]["warning"] is None


def test_start_after_plans_only_the_rest_of_today(client, alice):
    task(client, alice, "a")
    assert task_blocks(generate(client, alice, start_after_min=14 * H + 2))[0]["start_min"] == 14 * H + 5


def test_fixed_commitments_are_planned_around(client, alice):
    client.post(BLOCKS, json={"date": DAY, "title": "Lecture", "start_min": 9 * H, "end_min": 11 * H}, headers=alice)
    task(client, alice, "a")
    plan = generate(client, alice)
    assert task_blocks(plan)[0]["start_min"] >= 11 * H
    assert any(b["kind"] == "fixed" and b["title"] == "Lecture" for b in plan["blocks"])


def test_regenerating_replaces_unlocked_blocks_without_duplicating(client, alice):
    task(client, alice, "a")
    first = generate(client, alice)
    second = generate(client, alice)
    assert len(task_blocks(second)) == 1 == len(task_blocks(first))
    assert len(client.get(PLAN, params={"date": DAY}, headers=alice).json()["blocks"]) == len(second["blocks"])


def test_user_adjusted_blocks_are_pinned_and_survive_recalculation(client, alice):
    task(client, alice, "a", importance=5)
    task(client, alice, "b", importance=1)
    plan = generate(client, alice)
    block_a = next(x for x in task_blocks(plan) if x["title"] == "a")
    res = client.patch(f"{BLOCKS}/{block_a['id']}", json={"start_min": 14 * H, "end_min": 15 * H}, headers=alice)
    assert res.status_code == 200 and res.json()["pinned"] is True
    again = generate(client, alice)
    pinned = next(x for x in task_blocks(again) if x["title"] == "a")
    assert (pinned["start_min"], pinned["end_min"]) == (14 * H, 15 * H)
    others = [x for x in task_blocks(again) if x["title"] == "b"]
    assert len(others) == 1
    assert not (others[0]["start_min"] < 15 * H and 14 * H < others[0]["end_min"])  # planned around the pinned block


def test_changing_a_time_block_cannot_overlap_another(client, alice):
    task(client, alice, "a"), task(client, alice, "b")
    blocks = task_blocks(generate(client, alice))
    first, second = blocks
    res = client.patch(f"{BLOCKS}/{second['id']}", json={"start_min": first["start_min"] + 10}, headers=alice)
    assert res.status_code == 409
    assert client.patch(f"{BLOCKS}/{second['id']}", json={"start_min": 1000, "end_min": 990}, headers=alice).status_code == 422


@pytest.mark.parametrize("direction", ["up", "down"])
def test_reorder_swaps_neighbours_without_overlap_or_leaving_the_span(client, alice, direction):
    task(client, alice, "a", 30, importance=5), task(client, alice, "b", 90, importance=1)
    first, second = task_blocks(generate(client, alice))
    target = second if direction == "up" else first
    res = client.post(f"{BLOCKS}/{target['id']}/move", json={"direction": direction}, headers=alice)
    assert res.status_code == 200
    moved = task_blocks(client.get(PLAN, params={"date": DAY}, headers=alice).json())
    assert [b["title"] for b in moved] == ["b", "a"]
    assert moved[0]["start_min"] == first["start_min"] and moved[1]["end_min"] <= second["end_min"]  # stays in its span
    assert moved[0]["end_min"] <= moved[1]["start_min"] and all(b["pinned"] for b in moved)


def test_cannot_move_past_the_ends(client, alice):
    task(client, alice, "a"), task(client, alice, "b")
    first, second = task_blocks(generate(client, alice))
    assert client.post(f"{BLOCKS}/{first['id']}/move", json={"direction": "up"}, headers=alice).status_code == 409
    assert client.post(f"{BLOCKS}/{second['id']}/move", json={"direction": "down"}, headers=alice).status_code == 409


def test_completing_a_block_completes_the_task(client, alice):
    t = task(client, alice, "a")
    block = task_blocks(generate(client, alice))[0]
    res = client.patch(f"{BLOCKS}/{block['id']}", json={"done": True}, headers=alice)
    assert res.status_code == 200 and res.json()["done"] is True
    assert client.get(f"{T}/{t['id']}", headers=alice).json()["status"] == "completed"
    kept = task_blocks(generate(client, alice))
    assert len(kept) == 1 and kept[0]["done"] is True  # finished work stays on the day
    client.patch(f"{BLOCKS}/{block['id']}", json={"done": False}, headers=alice)
    assert client.get(f"{T}/{t['id']}", headers=alice).json()["status"] == "in_progress"


def test_postponed_task_is_excluded_until_brought_back(client, alice):
    task(client, alice, "a"), task(client, alice, "b")
    block = task_blocks(generate(client, alice))[0]
    res = client.post(f"{BLOCKS}/{block['id']}/postpone", json={}, headers=alice)
    assert res.status_code == 200 and res.json()["kind"] == "postponed"
    titles = [b["title"] for b in task_blocks(generate(client, alice))]
    assert block["title"] not in titles and len(titles) == 1
    assert client.delete(f"{BLOCKS}/{block['id']}", headers=alice).status_code == 204  # bring it back
    assert block["title"] in [b["title"] for b in task_blocks(generate(client, alice))]


def test_postponed_blocks_do_not_count_as_busy_time(client, alice):
    task(client, alice, "a", 60)
    block = task_blocks(generate(client, alice))[0]
    client.post(f"{BLOCKS}/{block['id']}/postpone", json={}, headers=alice)
    plan = client.get(PLAN, params={"date": DAY}, headers=alice).json()
    assert plan["free_minutes"] == 480 and plan["planned_minutes"] == 0


def test_fixed_block_validation_and_overlap(client, alice):
    ok = client.post(BLOCKS, json={"date": DAY, "title": "Gym", "start_min": 600, "end_min": 660}, headers=alice)
    assert ok.status_code == 201
    assert client.post(BLOCKS, json={"date": DAY, "title": "Clash", "start_min": 630, "end_min": 700}, headers=alice).status_code == 409
    assert client.post(BLOCKS, json={"date": DAY, "title": "Bad", "start_min": 700, "end_min": 700}, headers=alice).status_code == 422
    assert client.post(BLOCKS, json={"date": DAY, "title": " ", "start_min": 1, "end_min": 2}, headers=alice).status_code == 422
    assert client.delete(f"{BLOCKS}/{ok.json()['id']}", headers=alice).status_code == 204


def test_planner_preferences_change_the_window(client, alice):
    url = "/api/v1/preferences/planner"
    assert client.get(url, headers=alice).json() == {"workday_start_min": 540, "workday_end_min": 1020, "break_minutes": 10}
    assert client.put(url, json={"workday_start_min": 600, "workday_end_min": 660, "break_minutes": 0}, headers=alice).status_code == 200
    task(client, alice, "a", 30), task(client, alice, "b", 30)
    plan = generate(client, alice)
    assert plan["window_start"] == 600 and all(b["end_min"] <= 660 for b in plan["blocks"])
    for bad in ({"workday_start_min": 600, "workday_end_min": 610, "break_minutes": 5},
                {"workday_start_min": 600, "workday_end_min": 900, "break_minutes": 99}):
        assert client.put(url, json=bad, headers=alice).status_code == 422


def test_empty_day_is_fine(client, alice):
    plan = generate(client, alice)
    assert plan["blocks"] == [] and plan["unscheduled_total"] == 0


def test_plans_are_private_to_each_user(client, alice, bob):
    task(client, alice, "secret")
    block = task_blocks(generate(client, alice))[0]
    assert client.get(PLAN, params={"date": DAY}, headers=bob).json()["blocks"] == []
    assert task_blocks(generate(client, bob)) == []
    for method, url, body in [
        ("patch", f"{BLOCKS}/{block['id']}", {"done": True}),
        ("post", f"{BLOCKS}/{block['id']}/move", {"direction": "down"}),
        ("post", f"{BLOCKS}/{block['id']}/postpone", {}),
        ("delete", f"{BLOCKS}/{block['id']}", None),
    ]:
        res = getattr(client, method)(url, headers=bob, **({"json": body} if body is not None else {}))
        assert res.status_code == 404, (method, url)
    assert client.get(f"{T}", headers=alice).json()[0]["status"] == "not_started"


def test_planner_needs_no_ai_even_when_ai_is_off(make_client, alice):
    client = make_client(None, gemini_api_key="")
    task(client, alice, "a")
    assert len(task_blocks(generate(client, alice))) == 1


def test_requires_authentication(client):
    assert client.post(GEN, json={"date": DAY}).status_code == 401
    assert client.get(PLAN, params={"date": DAY}).status_code == 401
