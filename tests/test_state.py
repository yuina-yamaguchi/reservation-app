def test_state_requires_login(client):
    response = client.get("/api/state/")
    assert response.status_code == 401


def test_state_returns_admin_data(auth_client):
    car = auth_client.post(
        "/api/cars/",
        json={"name": "テスト車", "plate": "1234", "color": "赤"},
    ).json()
    member = auth_client.post("/api/members/", json={"name": "山田"}).json()
    auth_client.post(
        "/api/reservations/",
        json={
            "car_id": car["id"],
            "member_id": member["id"],
            "start_time": "2026-11-03T09:00:00",
            "end_time": "2026-11-03T10:00:00",
            "note": "",
        },
    )

    response = auth_client.get("/api/state/")

    assert response.status_code == 200
    data = response.json()
    assert len(data["cars"]) == 1
    assert len(data["members"]) == 1
    assert len(data["reservations"]) == 1
    assert data["reservations"][0]["car"]["name"] == "テスト車"
    assert data["reservations"][0]["member"]["name"] == "山田"
    assert len(data["users"]) == 1
    assert data["users"][0]["username"] == "admin"


def test_state_hides_users_for_regular_user(auth_client):
    auth_client.post(
        "/api/users/",
        json={
            "username": "user1",
            "password": "password123",
            "role": "user",
        },
    )
    auth_client.post("/api/auth/logout")

    login = auth_client.post(
        "/api/auth/login",
        json={"username": "user1", "password": "password123"},
    )
    assert login.status_code == 200

    response = auth_client.get("/api/state/")

    assert response.status_code == 200
    data = response.json()
    assert data["cars"] == []
    assert data["members"] == []
    assert data["reservations"] == []
    assert data["users"] == []
