from datetime import datetime, timedelta


def create_car(client, name="プリウス"):
    response = client.post(
        "/api/cars/",
        json={"name": name, "plate": "品川 300 あ 1234", "color": "白"},
    )
    assert response.status_code == 201
    return response.json()


def create_member(client, name="山田"):
    response = client.post("/api/members/", json={"name": name})
    assert response.status_code == 201
    return response.json()


def create_user(
    client,
    username="resident",
    password="password123",
    role="user",
    member_id=None,
):
    response = client.post(
        "/api/users/",
        json={
            "username": username,
            "password": password,
            "role": role,
            "member_id": member_id,
        },
    )
    assert response.status_code == 201
    return response.json()


def login(client, username, password):
    return client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )


def create_reservation(client, car_id, member_id, start=None, hours=1):
    if start is None:
        start = (datetime.now() + timedelta(days=3)).replace(
            hour=10, minute=0, second=0, microsecond=0
        )
    return client.post(
        "/api/reservations/",
        json={
            "car_id": car_id,
            "member_id": member_id,
            "start_time": start.isoformat(),
            "end_time": (start + timedelta(hours=hours)).isoformat(),
            "note": "",
        },
    )


def test_admin_can_create_user(auth_client):
    member = create_member(auth_client)
    user = create_user(auth_client, member_id=member["id"])

    assert user["role"] == "user"
    assert user["member_id"] == member["id"]
    assert user["member_name"] == "山田"


def test_user_cannot_manage_cars_or_users(auth_client):
    member = create_member(auth_client)
    create_user(auth_client, member_id=member["id"])
    auth_client.post("/api/auth/logout")

    assert login(auth_client, "resident", "password123").status_code == 200
    assert auth_client.get("/api/cars/").status_code == 200
    assert (
        auth_client.post(
            "/api/cars/",
            json={"name": "ヴォクシー", "plate": "1234", "color": "黒"},
        ).status_code
        == 403
    )
    assert auth_client.post("/api/members/", json={"name": "佐藤"}).status_code == 403
    assert auth_client.get("/api/users/").status_code == 403


def test_user_reservation_is_forced_to_linked_member(auth_client):
    own_member = create_member(auth_client, "山田")
    other_member = create_member(auth_client, "佐藤")
    car = create_car(auth_client)
    create_user(auth_client, member_id=own_member["id"])
    auth_client.post("/api/auth/logout")

    assert login(auth_client, "resident", "password123").status_code == 200
    response = create_reservation(
        auth_client, car["id"], other_member["id"]
    )

    assert response.status_code == 201
    assert response.json()["member"]["id"] == own_member["id"]


def test_user_cannot_cancel_another_members_reservation(auth_client):
    own_member = create_member(auth_client, "山田")
    other_member = create_member(auth_client, "佐藤")
    car = create_car(auth_client)
    create_user(auth_client, member_id=own_member["id"])
    reservation = create_reservation(auth_client, car["id"], other_member["id"])
    assert reservation.status_code == 201
    reservation_id = reservation.json()["id"]

    auth_client.post("/api/auth/logout")
    assert login(auth_client, "resident", "password123").status_code == 200
    assert (
        auth_client.delete(f"/api/reservations/{reservation_id}").status_code
        == 403
    )


def test_user_can_cancel_own_reservation(auth_client):
    member = create_member(auth_client)
    car = create_car(auth_client)
    create_user(auth_client, member_id=member["id"])
    auth_client.post("/api/auth/logout")
    assert login(auth_client, "resident", "password123").status_code == 200

    reservation = create_reservation(auth_client, car["id"], member["id"])
    assert reservation.status_code == 201
    assert (
        auth_client.delete(
            f"/api/reservations/{reservation.json()['id']}"
        ).status_code
        == 204
    )


def test_user_without_member_cannot_reserve(auth_client):
    car = create_car(auth_client)
    create_user(auth_client, member_id=None)
    auth_client.post("/api/auth/logout")
    assert login(auth_client, "resident", "password123").status_code == 200

    response = create_reservation(auth_client, car["id"], 1)
    assert response.status_code == 403


def test_last_admin_cannot_be_demoted_or_deleted(auth_client):
    me = auth_client.get("/api/auth/me").json()["user"]

    demote = auth_client.put(
        f"/api/users/{me['id']}", json={"role": "user"}
    )
    assert demote.status_code == 409

    delete = auth_client.delete(f"/api/users/{me['id']}")
    assert delete.status_code == 409


def test_member_with_linked_user_cannot_be_deleted(auth_client):
    member = create_member(auth_client)
    create_user(auth_client, member_id=member["id"])

    response = auth_client.delete(f"/api/members/{member['id']}")
    assert response.status_code == 409
