from datetime import datetime, timedelta


def create_car(client, name="プリウス"):
    response = client.post(
        "/api/cars/",
        json={
            "name": name,
            "plate": "品川 300 あ 1234",
            "color": "白",
        },
    )
    assert response.status_code == 201
    return response.json()


def create_member(client, name="101"):
    response = client.post("/api/members/", json={"name": name})
    assert response.status_code == 201
    return response.json()


def create_reservation(client, car_id, member_id, start, end, note=""):
    return client.post(
        "/api/reservations/",
        json={
            "car_id": car_id,
            "member_id": member_id,
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "note": note,
        },
    )


def test_requires_login(client):
    response = client.get("/api/reservations/")
    assert response.status_code == 401


def test_member_accepts_room_number_or_surname(auth_client):
    for name in ("101", "山田"):
        response = auth_client.post("/api/members/", json={"name": name})
        assert response.status_code == 201
        assert response.json()["name"] == name


def test_create_and_list_reservation(auth_client):
    car = create_car(auth_client)
    member = create_member(auth_client)
    start = datetime(2027, 1, 10, 10, 0)
    end = start + timedelta(hours=2)

    response = create_reservation(
        auth_client, car["id"], member["id"], start, end, note="買い物"
    )
    assert response.status_code == 201

    data = response.json()
    assert data["car"]["id"] == car["id"]
    assert data["member"]["id"] == member["id"]
    assert data["note"] == "買い物"

    listed = auth_client.get("/api/reservations/")
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_conflicting_reservation_returns_409(auth_client):
    car = create_car(auth_client)
    member = create_member(auth_client)
    start = datetime(2027, 1, 10, 10, 0)
    end = start + timedelta(hours=2)

    first = create_reservation(auth_client, car["id"], member["id"], start, end)
    assert first.status_code == 201

    overlap = create_reservation(
        auth_client,
        car["id"],
        member["id"],
        start + timedelta(minutes=30),
        end + timedelta(hours=1),
    )
    assert overlap.status_code == 409

    adjacent = create_reservation(
        auth_client,
        car["id"],
        member["id"],
        end,
        end + timedelta(hours=1),
    )
    assert adjacent.status_code == 201


def test_end_time_must_be_after_start_time(auth_client):
    car = create_car(auth_client)
    member = create_member(auth_client)
    start = datetime(2027, 1, 10, 10, 0)

    response = create_reservation(
        auth_client, car["id"], member["id"], start, start
    )
    assert response.status_code == 422


def test_cancel_reservation(auth_client):
    car = create_car(auth_client)
    member = create_member(auth_client)
    start = datetime(2027, 2, 1, 9, 0)

    created = create_reservation(
        auth_client, car["id"], member["id"], start, start + timedelta(hours=1)
    )
    reservation_id = created.json()["id"]

    deleted = auth_client.delete(f"/api/reservations/{reservation_id}")
    assert deleted.status_code == 204
    assert auth_client.get("/api/reservations/").json() == []


def test_cannot_delete_car_with_reservation(auth_client):
    car = create_car(auth_client)
    member = create_member(auth_client)
    start = datetime(2027, 3, 1, 9, 0)

    create_reservation(
        auth_client, car["id"], member["id"], start, start + timedelta(hours=1)
    )

    response = auth_client.delete(f"/api/cars/{car['id']}")
    assert response.status_code == 409


def test_cannot_delete_member_with_reservation(auth_client):
    car = create_car(auth_client)
    member = create_member(auth_client)
    start = datetime(2027, 4, 1, 9, 0)

    create_reservation(
        auth_client, car["id"], member["id"], start, start + timedelta(hours=1)
    )

    response = auth_client.delete(f"/api/members/{member['id']}")
    assert response.status_code == 409
