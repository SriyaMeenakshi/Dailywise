import uuid

T = "/api/v1/tasks"
P = "/api/v1/projects"


def task(client, h, **body):
    body.setdefault("title", "A task")
    res = client.post(T, json=body, headers=h)
    assert res.status_code == 201, res.text
    return res.json()


def project(client, h, **body):
    body.setdefault("name", "Capstone")
    res = client.post(P, json=body, headers=h)
    assert res.status_code == 201, res.text
    return res.json()


def phase(client, h, project_id, name="Design"):
    res = client.post(f"{P}/{project_id}/phases", json={"name": name}, headers=h)
    assert res.status_code == 201, res.text
    return res.json()


def test_project_crud(client, alice):
    p = project(client, alice, objective="Ship v1", deadline="2026-12-20T00:00:00Z")
    assert p["status"] == "active" and p["progress"]["percent"] == 0
    upd = client.patch(f"{P}/{p['id']}", json={"name": "Capstone v2", "deadline": None}, headers=alice).json()
    assert upd["name"] == "Capstone v2" and upd["deadline"] is None and upd["objective"] == "Ship v1"
    assert client.patch(f"{P}/{p['id']}", json={"name": None}, headers=alice).status_code == 422
    assert client.post(P, json={"name": "  "}, headers=alice).status_code == 422
    assert client.delete(f"{P}/{p['id']}", headers=alice).status_code == 204
    assert client.get(f"{P}/{p['id']}", headers=alice).status_code == 404


def test_phases_are_ordered_and_deleting_keeps_tasks(client, alice):
    p = project(client, alice)
    a, b = phase(client, alice, p["id"], "Design"), phase(client, alice, p["id"], "Build")
    assert (a["sort_order"], b["sort_order"]) == (1, 2)
    t = task(client, alice, project_id=p["id"], phase_id=a["id"])
    assert [x["name"] for x in client.get(f"{P}/{p['id']}", headers=alice).json()["phases"]] == ["Design", "Build"]
    assert client.delete(f"/api/v1/phases/{a['id']}", headers=alice).status_code == 204
    after = client.get(f"{T}/{t['id']}", headers=alice).json()
    assert after["phase_id"] is None and after["project_id"] == p["id"]


def test_deleting_project_keeps_tasks(client, alice):
    p = project(client, alice)
    t = task(client, alice, project_id=p["id"])
    client.delete(f"{P}/{p['id']}", headers=alice)
    assert client.get(f"{T}/{t['id']}", headers=alice).json()["project_id"] is None


def test_project_progress_is_weighted_by_effort(client, alice):
    p = project(client, alice)
    small = task(client, alice, title="small", project_id=p["id"], estimated_minutes=30)
    task(client, alice, title="big", project_id=p["id"], estimated_minutes=270)
    client.patch(f"{T}/{small['id']}", json={"status": "completed"}, headers=alice)
    prog = client.get(f"{P}/{p['id']}", headers=alice).json()["progress"]
    assert prog["percent"] == 10.0
    assert (prog["tasks_done"], prog["tasks_total"], prog["remaining_minutes"]) == (1, 2, 270)
    listed = client.get(P, headers=alice).json()[0]["progress"]
    assert listed["percent"] == 10.0


def test_phase_progress_and_deadline_range(client, alice):
    p = project(client, alice)
    ph = phase(client, alice, p["id"])
    t = task(client, alice, project_id=p["id"], phase_id=ph["id"], estimated_minutes=60, deadline="2026-12-01T00:00:00Z")
    task(client, alice, project_id=p["id"], phase_id=ph["id"], estimated_minutes=60, deadline="2026-12-10T00:00:00Z")
    client.patch(f"{T}/{t['id']}", json={"status": "completed"}, headers=alice)
    detail = client.get(f"{P}/{p['id']}", headers=alice).json()
    got = detail["phases"][0]
    assert got["progress"]["percent"] == 50.0
    assert got["earliest_deadline"].startswith("2026-12-01") and got["latest_deadline"].startswith("2026-12-10")


def test_subtasks_feed_progress(client, alice):
    p = project(client, alice)
    t = task(client, alice, project_id=p["id"], estimated_minutes=100)
    s1 = client.post(f"{T}/{t['id']}/subtasks", json={"title": "outline", "estimated_minutes": 30}, headers=alice).json()
    client.post(f"{T}/{t['id']}/subtasks", json={"title": "write", "estimated_minutes": 10}, headers=alice)
    assert client.patch(f"/api/v1/subtasks/{s1['id']}", json={"done": True}, headers=alice).json()["done"] is True
    assert client.get(f"{P}/{p['id']}", headers=alice).json()["progress"]["done_minutes"] == 75
    subs = client.get(f"{T}/{t['id']}/subtasks", headers=alice).json()
    assert [s["title"] for s in subs] == ["outline", "write"]
    assert client.delete(f"/api/v1/subtasks/{s1['id']}", headers=alice).status_code == 204


def test_task_must_use_own_project_and_matching_phase(client, alice, bob):
    pa, pb = project(client, alice), project(client, bob)
    other = project(client, alice, name="Other")
    ph_other = phase(client, alice, other["id"])
    assert client.post(T, json={"title": "x", "project_id": pb["id"]}, headers=alice).status_code == 422
    bad = {"title": "x", "project_id": pa["id"], "phase_id": ph_other["id"]}
    assert client.post(T, json=bad, headers=alice).status_code == 422
    derived = task(client, alice, phase_id=ph_other["id"])
    assert derived["project_id"] == other["id"]


def test_moving_task_to_another_project_clears_its_phase(client, alice):
    a, b = project(client, alice), project(client, alice, name="B")
    ph = phase(client, alice, a["id"])
    t = task(client, alice, project_id=a["id"], phase_id=ph["id"])
    moved = client.patch(f"{T}/{t['id']}", json={"project_id": b["id"]}, headers=alice).json()
    assert moved["project_id"] == b["id"] and moved["phase_id"] is None


def test_filter_tasks_by_project(client, alice):
    p = project(client, alice)
    task(client, alice, title="in", project_id=p["id"])
    task(client, alice, title="out")
    res = client.get(T, params={"project_id": p["id"]}, headers=alice).json()
    assert [x["title"] for x in res] == ["in"]


def test_dependencies_add_remove_and_blocking_boost(client, alice):
    base = task(client, alice, title="base")
    dependent = task(client, alice, title="dependent")
    before = client.get(f"{T}/{base['id']}", headers=alice).json()["priority_score"]
    res = client.post(f"{T}/{dependent['id']}/dependencies", json={"depends_on_id": base["id"]}, headers=alice)
    assert res.status_code == 201 and res.json()["dependency_ids"] == [base["id"]] and res.json()["waiting_on_count"] == 1
    boosted = client.get(f"{T}/{base['id']}", headers=alice).json()["priority_score"]
    assert boosted > before
    assert client.post(f"{T}/{dependent['id']}/dependencies", json={"depends_on_id": base["id"]}, headers=alice).status_code == 409
    client.delete(f"{T}/{dependent['id']}/dependencies/{base['id']}", headers=alice)
    assert client.get(f"{T}/{base['id']}", headers=alice).json()["priority_score"] == before
    assert client.delete(f"{T}/{dependent['id']}/dependencies/{base['id']}", headers=alice).status_code == 404


def test_completing_prerequisite_clears_waiting_count(client, alice):
    a, b = task(client, alice, title="a"), task(client, alice, title="b")
    client.post(f"{T}/{b['id']}/dependencies", json={"depends_on_id": a["id"]}, headers=alice)
    client.patch(f"{T}/{a['id']}", json={"status": "completed"}, headers=alice)
    assert client.get(f"{T}/{b['id']}", headers=alice).json()["waiting_on_count"] == 0


def test_completing_dependent_removes_blocking_boost(client, alice):
    a, b = task(client, alice, title="a"), task(client, alice, title="b")
    base = client.get(f"{T}/{a['id']}", headers=alice).json()["priority_score"]
    client.post(f"{T}/{b['id']}/dependencies", json={"depends_on_id": a["id"]}, headers=alice)
    client.patch(f"{T}/{b['id']}", json={"status": "completed"}, headers=alice)
    assert client.get(f"{T}/{a['id']}", headers=alice).json()["priority_score"] == base


def test_dependency_cycles_and_self_dependency_rejected(client, alice):
    a, b, c = (task(client, alice, title=n) for n in "abc")
    dep = lambda x, y: client.post(f"{T}/{x['id']}/dependencies", json={"depends_on_id": y["id"]}, headers=alice)  # noqa: E731
    assert dep(a, a).status_code == 422
    assert dep(a, b).status_code == 201 and dep(b, c).status_code == 201
    assert dep(c, a).status_code == 422  # a -> b -> c -> a
    assert dep(c, b).status_code == 422


def test_cannot_depend_on_someone_elses_task(client, alice, bob):
    mine, theirs = task(client, alice), task(client, bob)
    res = client.post(f"{T}/{mine['id']}/dependencies", json={"depends_on_id": theirs["id"]}, headers=alice)
    assert res.status_code == 404


def test_history_records_creation_and_changes(client, alice):
    t = task(client, alice, title="Essay")
    client.patch(f"{T}/{t['id']}", json={"status": "in_progress", "importance": 5}, headers=alice)
    client.patch(f"{T}/{t['id']}", json={"title": "Essay"}, headers=alice)  # no change -> no entry
    hist = client.get(f"{T}/{t['id']}/history", headers=alice).json()
    assert [h["action"] for h in hist] == ["status_changed", "created"]
    assert hist[0]["detail"]["status"] == {"from": "inbox", "to": "in_progress"}
    assert hist[0]["detail"]["importance"] == {"from": 3, "to": 5}


def test_priority_fields_explanation_and_levels(client, alice):
    t = task(client, alice, importance=5, urgency=5, impact=5, deadline="2020-01-01T00:00:00Z")
    assert t["priority_level"] == "critical" and t["priority_score"] > 75
    assert {f["key"] for f in t["priority_factors"]} == {"importance", "urgency", "deadline", "impact", "blocking"}
    assert "overdue" in t["priority_explanation"]


def test_priority_override_and_clearing(client, alice):
    t = task(client, alice, importance=1, urgency=1, impact=1)
    low = t["priority_score"]
    over = client.patch(f"{T}/{t['id']}", json={"priority_override": 90}, headers=alice).json()
    assert over["priority_score"] == 90 and over["priority_computed"] == low and over["priority_level"] == "critical"
    cleared = client.patch(f"{T}/{t['id']}", json={"priority_override": None}, headers=alice).json()
    assert cleared["priority_score"] == low and cleared["priority_override"] is None
    assert client.patch(f"{T}/{t['id']}", json={"priority_override": 101}, headers=alice).status_code == 422


def test_completed_task_drops_to_zero_and_leaves_ranking(client, alice):
    t = task(client, alice, importance=5, urgency=5)
    done = client.patch(f"{T}/{t['id']}", json={"status": "completed"}, headers=alice).json()
    assert done["priority_score"] == 0
    assert client.get("/api/v1/priorities", headers=alice).json() == []


def test_priorities_endpoint_ranks_and_sort_param_agrees(client, alice):
    task(client, alice, title="low", importance=1, urgency=1, impact=1)
    task(client, alice, title="top", importance=5, urgency=5, impact=5, deadline="2020-01-01T00:00:00Z")
    task(client, alice, title="mid", importance=3)
    ranked = [t["title"] for t in client.get("/api/v1/priorities", headers=alice).json()]
    assert ranked == ["top", "mid", "low"]
    by_sort = client.get(T, params={"sort": "priority", "order": "desc"}, headers=alice).json()
    assert [t["title"] for t in by_sort] == ranked


def test_missing_deadline_ranks_below_same_task_with_near_deadline(client, alice):
    task(client, alice, title="none")
    task(client, alice, title="soon", deadline="2999-01-01T00:00:00Z")
    near = task(client, alice, title="near", deadline="2020-01-01T00:00:00Z")
    ranked = [t["title"] for t in client.get("/api/v1/priorities", headers=alice).json()]
    assert ranked[0] == near["title"] and ranked.index("soon") != 0


def test_custom_weights_change_ranking_then_reset(client, alice):
    task(client, alice, title="important", importance=5, urgency=1, impact=1)
    task(client, alice, title="urgent", importance=1, urgency=5, impact=1)
    url = "/api/v1/preferences/priority-weights"
    default = client.get(url, headers=alice).json()
    assert default["is_custom"] is False and default["weights"]["importance"] == 0.25
    top = lambda: client.get("/api/v1/priorities", headers=alice).json()[0]["title"]  # noqa: E731
    assert top() == "important"  # importance weighs more than urgency by default
    res = client.put(url, json={"importance": 0, "urgency": 1, "deadline": 0, "impact": 0, "blocking": 0}, headers=alice)
    assert res.status_code == 200 and res.json()["weights"]["urgency"] == 1
    assert top() == "urgent"
    assert client.put(url, json={"importance": 0, "urgency": 0, "deadline": 0, "impact": 0, "blocking": 0}, headers=alice).status_code == 422
    assert client.put(url, json={"importance": -1, "urgency": 1, "deadline": 1, "impact": 1, "blocking": 1}, headers=alice).status_code == 422
    assert client.delete(url, headers=alice).json()["is_custom"] is False
    assert top() == "important"


def test_phase2_data_is_isolated_between_users(client, alice, bob):
    p = project(client, alice)
    ph = phase(client, alice, p["id"])
    t = task(client, alice, project_id=p["id"])
    sub = client.post(f"{T}/{t['id']}/subtasks", json={"title": "s"}, headers=alice).json()
    urls = [
        ("get", f"{P}/{p['id']}"), ("patch", f"{P}/{p['id']}"), ("delete", f"{P}/{p['id']}"),
        ("post", f"{P}/{p['id']}/phases"), ("patch", f"/api/v1/phases/{ph['id']}"),
        ("delete", f"/api/v1/phases/{ph['id']}"), ("get", f"{T}/{t['id']}/subtasks"),
        ("post", f"{T}/{t['id']}/subtasks"), ("patch", f"/api/v1/subtasks/{sub['id']}"),
        ("delete", f"/api/v1/subtasks/{sub['id']}"), ("get", f"{T}/{t['id']}/history"),
    ]
    for method, url in urls:
        res = getattr(client, method)(url, headers=bob, **({"json": {"name": "x", "title": "x"}} if method in {"post", "patch"} else {}))
        assert res.status_code == 404, (method, url, res.status_code)
    assert client.get(P, headers=bob).json() == []
    assert client.get("/api/v1/priorities", headers=bob).json() == []
    assert client.get(f"{P}/{uuid.uuid4()}", headers=alice).status_code == 404
