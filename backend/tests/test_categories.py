API = "/api/v1/categories"


def test_create_update_delete_category(client, alice):
    res = client.post(API, json={"name": "Side hustle", "color": "#112233"}, headers=alice)
    assert res.status_code == 201
    cat = res.json()
    renamed = client.patch(f"{API}/{cat['id']}", json={"name": "Freelance"}, headers=alice).json()
    assert renamed["name"] == "Freelance" and renamed["color"] == "#112233"
    assert client.delete(f"{API}/{cat['id']}", headers=alice).status_code == 204
    assert "Freelance" not in [c["name"] for c in client.get(API, headers=alice).json()]


def test_duplicate_name_conflicts_but_other_users_may_reuse(client, alice, bob):
    assert client.post(API, json={"name": "Academic"}, headers=alice).status_code == 409
    client.get(API, headers=bob)
    assert client.post(API, json={"name": "Custom"}, headers=bob).status_code == 201
    assert client.post(API, json={"name": "Custom"}, headers=alice).status_code == 201


def test_invalid_color_rejected(client, alice):
    assert client.post(API, json={"name": "x", "color": "red"}, headers=alice).status_code == 422


def test_other_users_cannot_modify_category(client, alice, bob):
    alice_cat = client.get(API, headers=alice).json()[0]
    client.get(API, headers=bob)
    assert client.patch(f"{API}/{alice_cat['id']}", json={"name": "x"}, headers=bob).status_code == 404
    assert client.delete(f"{API}/{alice_cat['id']}", headers=bob).status_code == 404


def test_deleting_category_keeps_tasks_uncategorised(client, alice):
    cat = client.get(API, headers=alice).json()[0]
    task = client.post(
        "/api/v1/tasks", json={"title": "t", "category_id": cat["id"]}, headers=alice
    ).json()
    assert client.delete(f"{API}/{cat['id']}", headers=alice).status_code == 204
    after = client.get(f"/api/v1/tasks/{task['id']}", headers=alice).json()
    assert after["category_id"] is None
