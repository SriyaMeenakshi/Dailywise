import uuid

API = "/api/v1/tasks"


def create(client, headers, **body):
    body.setdefault("title", "Write DBMS assignment")
    res = client.post(API, json=body, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def first_category_id(client, headers) -> str:
    return client.get("/api/v1/categories", headers=headers).json()[0]["id"]


def test_quick_capture_needs_only_a_title(client, alice):
    task = create(client, alice, title="  Buy notebook  ")
    assert task["title"] == "Buy notebook"
    assert task["status"] == "inbox"
    assert (task["importance"], task["urgency"], task["energy"]) == (3, 3, "medium")
    assert task["deadline"] is None and task["category_id"] is None


def test_create_with_all_fields(client, alice):
    cat = first_category_id(client, alice)
    task = create(
        client,
        alice,
        title="Study NLP",
        description="Chapters 3-4",
        expected_outcome="Notes done",
        notes="Use slides",
        category_id=cat,
        importance=5,
        urgency=2,
        energy="high",
        status="not_started",
        recurrence="weekly",
        deadline="2026-11-20T10:00:00Z",
        estimated_minutes=90,
    )
    assert task["category_id"] == cat and task["recurrence"] == "weekly"
    assert task["estimated_minutes"] == 90


BAD_BODIES = [
    {"title": "   "},
    {"title": ""},
    {"title": "x", "importance": 0},
    {"title": "x", "urgency": 6},
    {"title": "x", "status": "done"},
    {"title": "x", "estimated_minutes": 0},
    {"title": "x", "energy": "extreme"},
]


def test_validation_rejects_bad_input(client, alice):
    for body in BAD_BODIES:
        assert client.post(API, json=body, headers=alice).status_code == 422, body


def test_unknown_or_foreign_category_rejected(client, alice, bob):
    foreign = first_category_id(client, bob)
    assert client.post(API, json={"title": "x", "category_id": foreign}, headers=alice).status_code == 422
    assert (
        client.post(API, json={"title": "x", "category_id": str(uuid.uuid4())}, headers=alice).status_code
        == 422
    )


def test_partial_update_and_clearing_nullable_fields(client, alice):
    task = create(client, alice, deadline="2026-11-20T10:00:00Z", description="d")
    res = client.patch(f"{API}/{task['id']}", json={"importance": 5, "deadline": None}, headers=alice)
    body = res.json()
    assert res.status_code == 200
    assert body["importance"] == 5 and body["deadline"] is None
    assert body["description"] == "d" and body["title"] == task["title"]


def test_update_cannot_null_required_fields(client, alice):
    task = create(client, alice)
    assert client.patch(f"{API}/{task['id']}", json={"title": None}, headers=alice).status_code == 422
    assert client.patch(f"{API}/{task['id']}", json={"status": None}, headers=alice).status_code == 422


def test_completion_sets_and_clears_completed_at(client, alice):
    task = create(client, alice)
    done = client.patch(f"{API}/{task['id']}", json={"status": "completed"}, headers=alice).json()
    assert done["completed_at"] is not None
    reopened = client.patch(f"{API}/{task['id']}", json={"status": "in_progress"}, headers=alice).json()
    assert reopened["completed_at"] is None


def test_delete(client, alice):
    task = create(client, alice)
    assert client.delete(f"{API}/{task['id']}", headers=alice).status_code == 204
    assert client.get(f"{API}/{task['id']}", headers=alice).status_code == 404


def test_users_cannot_access_each_others_tasks(client, alice, bob):
    task = create(client, alice, title="Alice private")
    url = f"{API}/{task['id']}"
    assert client.get(url, headers=bob).status_code == 404
    assert client.patch(url, json={"title": "hacked"}, headers=bob).status_code == 404
    assert client.delete(url, headers=bob).status_code == 404
    assert client.get(API, headers=bob).json() == []
    assert client.get(url, headers=alice).json()["title"] == "Alice private"


def test_client_supplied_user_id_is_ignored(client, alice, bob):
    me_bob = client.get("/api/v1/me", headers=bob).json()["id"]
    res = client.post(API, json={"title": "x", "user_id": me_bob}, headers=alice)
    assert res.status_code == 201
    assert client.get(API, headers=bob).json() == []


def test_list_filters_search_and_default_hides_archived(client, alice):
    cat = first_category_id(client, alice)
    create(client, alice, title="Database assignment", category_id=cat, status="not_started")
    create(client, alice, title="Gym session", status="completed")
    create(client, alice, title="Old stuff", status="archived")

    titles = lambda **p: sorted(t["title"] for t in client.get(API, params=p, headers=alice).json())
    assert titles() == ["Database assignment", "Gym session"]
    assert titles(status="archived") == ["Old stuff"]
    assert titles(status=["not_started", "completed"]) == ["Database assignment", "Gym session"]
    assert titles(category_id=cat) == ["Database assignment"]
    assert titles(q="assign") == ["Database assignment"]
    assert titles(q="nothing-matches") == []


def test_sorting_keeps_tasks_without_deadline_last(client, alice):
    create(client, alice, title="no deadline")
    create(client, alice, title="late", deadline="2026-12-01T00:00:00Z")
    create(client, alice, title="soon", deadline="2026-11-05T00:00:00Z")
    for order in ("asc", "desc"):
        res = client.get(API, params={"sort": "deadline", "order": order}, headers=alice).json()
        assert res[-1]["title"] == "no deadline"
    asc = client.get(API, params={"sort": "deadline", "order": "asc"}, headers=alice).json()
    assert [t["title"] for t in asc[:2]] == ["soon", "late"]


def test_invalid_query_params_rejected(client, alice):
    assert client.get(API, params={"sort": "password"}, headers=alice).status_code == 422
    assert client.get(API, params={"limit": 0}, headers=alice).status_code == 422


def test_unauthenticated_requests_rejected(client):
    assert client.get(API).status_code == 401
    assert client.post(API, json={"title": "x"}).status_code == 401
