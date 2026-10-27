def test_seed_requires_login(client):
    response = client.post("/api/admin/seed")
    assert response.status_code == 401


def test_seed_creates_default_data_once(auth_client):
    first = auth_client.post("/api/admin/seed")
    assert first.status_code == 200
    assert first.json()["cars_created"] == 3
    assert first.json()["members_created"] == 4

    second = auth_client.post("/api/admin/seed")
    assert second.status_code == 200
    assert second.json()["cars_created"] == 0
    assert second.json()["members_created"] == 0

    assert len(auth_client.get("/api/cars/").json()) == 3
    assert len(auth_client.get("/api/members/").json()) == 4


def test_seed_skips_existing_table(auth_client):
    auth_client.post("/api/cars/", json={"name": "既存車", "plate": "1234", "color": "赤"})
    response = auth_client.post("/api/admin/seed")
    assert response.status_code == 200
    assert response.json()["cars_created"] == 0
    assert response.json()["members_created"] == 4
