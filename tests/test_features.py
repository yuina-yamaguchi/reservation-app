from datetime import datetime, timedelta

from app import pricing

PASSWORD = "password123"
ADMIN_PASSWORD = "test-password"


def create_member(client, name):
    response = client.post("/api/members/", json={"name": name})
    assert response.status_code == 201
    return response.json()


def create_car(client, name="テスト車", seat_capacity=4):
    response = client.post(
        "/api/cars/",
        json={
            "name": name,
            "plate": "品川 300 あ 1234",
            "color": "白",
            "seat_capacity": seat_capacity,
        },
    )
    assert response.status_code == 201
    return response.json()


def create_user(client, username, member_id, role="user"):
    response = client.post(
        "/api/users/",
        json={
            "username": username,
            "password": PASSWORD,
            "role": role,
            "member_id": member_id,
        },
    )
    assert response.status_code == 201
    return response.json()


def set_plan(client, user_id, plan):
    response = client.put(f"/api/users/{user_id}/plan", json={"plan": plan})
    assert response.status_code == 200
    return response.json()


def set_profile(client, user_id, **payload):
    response = client.put(f"/api/users/{user_id}/profile", json=payload)
    assert response.status_code == 200
    return response.json()


def login(client, username, password=PASSWORD):
    response = client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200
    return response


def login_admin(client):
    login(client, "admin", ADMIN_PASSWORD)


def logout(client):
    client.post("/api/auth/logout")


def next_weekday(days=2):
    value = pricing.now_jst() + timedelta(days=days)
    while pricing.is_weekend_or_holiday(value):
        value += timedelta(days=1)
    return value.replace(hour=10, minute=0, second=0, microsecond=0)


def upcoming_weekend(weekday, weeks=0):
    today = pricing.now_jst()
    days = (weekday - today.weekday()) % 7
    if days == 0:
        days = 7
    value = today + timedelta(days=days + weeks * 7)
    return value.replace(hour=10, minute=0, second=0, microsecond=0)


def create_reservation(
    client, car_id, member_id, start, hours=1, payment_type="time"
):
    return client.post(
        "/api/reservations/",
        json={
            "car_id": car_id,
            "member_id": member_id,
            "start_time": start.isoformat(),
            "end_time": (start + timedelta(hours=hours)).isoformat(),
            "note": "",
            "payment_type": payment_type,
        },
    )


def options(client, car_id, member_id, start, hours=1):
    return client.post(
        "/api/reservations/options",
        json={
            "car_id": car_id,
            "member_id": member_id,
            "start_time": start.isoformat(),
            "end_time": (start + timedelta(hours=hours)).isoformat(),
        },
    )


def test_plan_and_tickets(auth_client):
    member = create_member(auth_client, "山田")
    user = create_user(auth_client, "resident", member["id"])

    updated = set_plan(auth_client, user["id"], "light")
    assert updated["plan"] == "light"

    tickets = auth_client.get(f"/api/users/{user['id']}/tickets").json()
    assert len(tickets) == 1
    assert tickets[0]["source"] == "included"
    assert tickets[0]["price"] == 3900
    assert tickets[0]["status"] == "available"
    expected_expiry = pricing.period_expiry(pricing.month_period(pricing.now_jst()))
    assert tickets[0]["expires_at"] == expected_expiry.isoformat()

    logout(auth_client)
    login(auth_client, "resident")
    purchased = auth_client.post(
        "/api/tickets/purchase", json={"source": "pack", "count": 1}
    )
    assert purchased.status_code == 201
    assert purchased.json()[0]["price"] == 4200

    logout(auth_client)
    login_admin(auth_client)
    granted = auth_client.post(
        f"/api/users/{user['id']}/tickets",
        json={"source": "extra", "count": 2},
    )
    assert granted.status_code == 201
    assert len(granted.json()) == 2
    assert all(ticket["price"] == 3800 for ticket in granted.json())


def test_self_service_plan_and_profile(auth_client):
    member = create_member(auth_client, "山田")
    other_member = create_member(auth_client, "鈴木")
    user = create_user(auth_client, "resident", member["id"])
    other = create_user(auth_client, "other", other_member["id"])

    logout(auth_client)
    login(auth_client, "resident")

    own_plan = auth_client.put(
        f"/api/users/{user['id']}/plan", json={"plan": "light"}
    )
    assert own_plan.status_code == 200
    assert own_plan.json()["plan"] == "light"

    own_profile = auth_client.put(
        f"/api/users/{user['id']}/profile",
        json={"gender": "female", "provider_recipient_id": "self-recipient"},
    )
    assert own_profile.status_code == 200
    assert own_profile.json()["gender"] == "female"
    assert own_profile.json()["provider_recipient_id"] == "self-recipient"

    forbidden_plan = auth_client.put(
        f"/api/users/{other['id']}/plan", json={"plan": "standard"}
    )
    assert forbidden_plan.status_code == 403
    forbidden_profile = auth_client.put(
        f"/api/users/{other['id']}/profile", json={"gender": "male"}
    )
    assert forbidden_profile.status_code == 403


def test_reservation_options_and_charge(auth_client):
    member = create_member(auth_client, "山田")
    car = create_car(auth_client)
    user = create_user(auth_client, "resident", member["id"])
    set_plan(auth_client, user["id"], "light")

    logout(auth_client)
    login(auth_client, "resident")

    start = next_weekday(2)
    data = options(auth_client, car["id"], member["id"], start)
    assert data.status_code == 200
    body = data.json()
    assert {option["type"] for option in body["options"]} == {"ticket", "time"}
    by_type = {option["type"]: option for option in body["options"]}
    assert by_type["ticket"]["total"] == 0
    assert by_type["ticket"]["vehicle_value"] == 3900
    assert by_type["time"]["total"] == 700

    created = create_reservation(
        auth_client, car["id"], member["id"], start, payment_type="ticket"
    )
    assert created.status_code == 201
    charge = created.json()["charge"]
    assert charge["payment_type"] == "ticket"
    assert charge["incremental_amount"] == 0
    assert charge["vehicle_value"] == 3900
    assert charge["actual_burden"] == 0

    adjacent = options(
        auth_client, car["id"], member["id"], start + timedelta(hours=1)
    )
    assert adjacent.json()["blocked_reason"] is not None

    after_buffer = create_reservation(
        auth_client,
        car["id"],
        member["id"],
        start + timedelta(hours=1, minutes=30),
        payment_type="time",
    )
    assert after_buffer.status_code == 201
    assert after_buffer.json()["charge"]["incremental_amount"] == 700


def test_booking_windows_and_weekend_limit(auth_client):
    member = create_member(auth_client, "山田")
    car = create_car(auth_client)
    user = create_user(auth_client, "resident", member["id"])

    logout(auth_client)
    login(auth_client, "resident")

    far = next_weekday(20)
    far_options = options(auth_client, car["id"], member["id"], far)
    assert far_options.status_code == 200
    assert far_options.json()["options"] == []
    assert far_options.json()["blocked_reason"] is not None

    saturday = upcoming_weekend(5)
    sunday = upcoming_weekend(6)
    next_saturday = upcoming_weekend(5, weeks=1)

    first = create_reservation(auth_client, car["id"], member["id"], saturday)
    second = create_reservation(auth_client, car["id"], member["id"], sunday)
    assert first.status_code == 201
    assert second.status_code == 201

    third_options = options(auth_client, car["id"], member["id"], next_saturday)
    assert third_options.status_code == 200
    assert "土日祝" in third_options.json()["blocked_reason"]


def test_carpool_flow_and_billing(auth_client):
    car = create_car(auth_client)
    driver_member = create_member(auth_client, "佐藤")
    passenger_member = create_member(auth_client, "鈴木")
    outsider_member = create_member(auth_client, "高橋")
    driver = create_user(auth_client, "driver", driver_member["id"])
    passenger = create_user(auth_client, "passenger", passenger_member["id"])
    outsider = create_user(auth_client, "outsider", outsider_member["id"])
    set_profile(auth_client, driver["id"], gender="male")
    set_profile(auth_client, passenger["id"], gender="female")
    set_profile(auth_client, outsider["id"], gender="male")

    logout(auth_client)
    login(auth_client, "driver")
    start = next_weekday(2)
    reservation = create_reservation(
        auth_client, car["id"], driver_member["id"], start
    )
    assert reservation.status_code == 201
    reservation_id = reservation.json()["id"]
    assert reservation.json()["charge"]["vehicle_value"] == 700

    ride = auth_client.post(
        "/api/carpools/",
        json={
            "reservation_id": reservation_id,
            "area": "far",
            "gender_filter": "female",
            "seats_offered": 2,
        },
    )
    assert ride.status_code == 201
    ride_id = ride.json()["id"]
    assert ride.json()["seat_fee"] == 500
    assert ride.json()["remaining_seats"] == 2

    logout(auth_client)
    login(auth_client, "passenger")
    application = auth_client.post(f"/api/carpools/{ride_id}/apply")
    assert application.status_code == 201
    application_id = application.json()["id"]
    assert application.json()["status"] == "pending"
    assert application.json()["seat_fee"] == 500

    logout(auth_client)
    login(auth_client, "outsider")
    rejected = auth_client.post(f"/api/carpools/{ride_id}/apply")
    assert rejected.status_code == 403

    logout(auth_client)
    login(auth_client, "driver")
    approved = auth_client.post(
        f"/api/carpools/{ride_id}/applications/{application_id}/approve"
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "accepted"

    logout(auth_client)
    login(auth_client, "passenger")
    billing = auth_client.get("/api/billing/me")
    assert billing.status_code == 200
    assert billing.json()["carpool_seat_fees_paid"] == 500
    assert billing.json()["total"] == 500

    logout(auth_client)
    login(auth_client, "driver")
    billing = auth_client.get("/api/billing/me")
    assert billing.status_code == 200
    body = billing.json()
    assert body["usage_charges"] == 700
    assert body["carpool_discount_received"] == 500
    assert body["total"] == 200

    updated = auth_client.put(
        f"/api/carpools/{ride_id}", json={"gender_filter": "any"}
    )
    assert updated.status_code == 200

    logout(auth_client)
    login(auth_client, "outsider")
    second_application = auth_client.post(f"/api/carpools/{ride_id}/apply")
    assert second_application.status_code == 201
    second_id = second_application.json()["id"]

    logout(auth_client)
    login(auth_client, "driver")
    over_cap = auth_client.post(
        f"/api/carpools/{ride_id}/applications/{second_id}/approve"
    )
    assert over_cap.status_code == 409


def test_notes_are_private_by_default_and_can_be_public(auth_client):
    car = create_car(auth_client, name="秘密車")
    public_car = create_car(auth_client, name="公開車")
    carpool_car = create_car(auth_client, name="相乗り車")
    owner_member = create_member(auth_client, "山田")
    other_member = create_member(auth_client, "鈴木")
    create_user(auth_client, "owner", owner_member["id"])
    create_user(auth_client, "other", other_member["id"])

    logout(auth_client)
    login(auth_client, "owner")
    start = next_weekday(2)
    private_note = auth_client.post(
        "/api/reservations/",
        json={
            "car_id": car["id"],
            "member_id": owner_member["id"],
            "start_time": start.isoformat(),
            "end_time": (start + timedelta(hours=1)).isoformat(),
            "note": "本人だけのメモ",
            "note_public": False,
            "payment_type": "time",
        },
    )
    assert private_note.status_code == 201
    private_note_id = private_note.json()["id"]
    assert private_note.json()["note"] == "本人だけのメモ"

    public_note = auth_client.post(
        "/api/reservations/",
        json={
            "car_id": public_car["id"],
            "member_id": owner_member["id"],
            "start_time": start.isoformat(),
            "end_time": (start + timedelta(hours=1)).isoformat(),
            "note": "公開メモ",
            "note_public": True,
            "payment_type": "time",
        },
    )
    assert public_note.status_code == 201
    public_note_id = public_note.json()["id"]
    assert public_note.json()["note"] == "公開メモ"

    carpool_reservation = create_reservation(
        auth_client, carpool_car["id"], owner_member["id"], start
    )
    assert carpool_reservation.status_code == 201
    carpool = auth_client.post(
        "/api/carpools/",
        json={
            "reservation_id": carpool_reservation.json()["id"],
            "note": "相乗りの秘密メモ",
            "note_public": False,
        },
    )
    assert carpool.status_code == 201
    carpool_id = carpool.json()["id"]
    assert carpool.json()["note"] == "相乗りの秘密メモ"
    assert carpool.json()["note_public"] is False

    owner_reservations = {
        item["id"]: item for item in auth_client.get("/api/reservations/").json()
    }
    assert owner_reservations[private_note_id]["note"] == "本人だけのメモ"
    assert owner_reservations[public_note_id]["note"] == "公開メモ"

    logout(auth_client)
    login(auth_client, "other")
    other_reservations = {
        item["id"]: item for item in auth_client.get("/api/reservations/").json()
    }
    assert other_reservations[private_note_id]["note"] == ""
    assert other_reservations[public_note_id]["note"] == "公開メモ"

    state = auth_client.get("/api/state/").json()
    state_reservations = {item["id"]: item for item in state["reservations"]}
    assert state_reservations[private_note_id]["note"] == ""
    assert state_reservations[public_note_id]["note"] == "公開メモ"

    other_carpools = {item["id"]: item for item in auth_client.get("/api/carpools/").json()}
    assert other_carpools[carpool_id]["note"] == ""
    assert other_carpools[carpool_id]["note_public"] is False

    logout(auth_client)
    login(auth_client, "owner")
    owner_carpools = {item["id"]: item for item in auth_client.get("/api/carpools/").json()}
    assert owner_carpools[carpool_id]["note"] == "相乗りの秘密メモ"

    updated = auth_client.put(
        f"/api/carpools/{carpool_id}", json={"note_public": True}
    )
    assert updated.status_code == 200
    assert updated.json()["note"] == "相乗りの秘密メモ"

    logout(auth_client)
    login(auth_client, "other")
    public_carpools = {item["id"]: item for item in auth_client.get("/api/carpools/").json()}
    assert public_carpools[carpool_id]["note"] == "相乗りの秘密メモ"
    assert public_carpools[carpool_id]["note_public"] is True

    logout(auth_client)
    login_admin(auth_client)
    admin_reservations = {
        item["id"]: item for item in auth_client.get("/api/reservations/").json()
    }
    assert admin_reservations[private_note_id]["note"] == ""


def test_digital_keys_and_audit(auth_client):
    car = create_car(auth_client)
    member = create_member(auth_client, "山田")
    user = create_user(auth_client, "resident", member["id"])
    admin_id = auth_client.get("/api/auth/me").json()["user"]["id"]
    set_profile(auth_client, admin_id, provider_recipient_id="admin-recipient")
    set_profile(auth_client, user["id"], provider_recipient_id="user-recipient")

    device = auth_client.post(
        "/api/key-devices/",
        json={
            "car_id": car["id"],
            "provider_device_id": "mock-device-1",
            "display_name": "テストキーボックス",
        },
    )
    assert device.status_code == 201
    assert auth_client.get("/api/cars/").json()[0]["key_supported"] is True

    logout(auth_client)
    login(auth_client, "resident")
    start = pricing.now_jst() + timedelta(hours=2)
    reservation = create_reservation(
        auth_client, car["id"], member["id"], start
    )
    assert reservation.status_code == 201
    key = reservation.json()["digital_key"]
    assert key["status"] == "issued"
    assert key["provider_key_id"].startswith("mock-")

    state = auth_client.get("/api/state/")
    assert state.status_code == 200
    state_body = state.json()
    assert len(state_body["plans"]) == 3
    assert len(state_body["key_devices"]) == 1
    assert len(state_body["digital_keys"]) == 1

    logout(auth_client)
    login_admin(auth_client)
    due = auth_client.post("/api/digital-keys/issue-due")
    assert due.status_code == 200

    master = auth_client.post(
        f"/api/digital-keys/cars/{car['id']}/master",
        json={
            "password": ADMIN_PASSWORD,
            "reason": "点検のため",
            "confirm_in_use": False,
        },
    )
    assert master.status_code == 201
    master_key = master.json()
    assert master_key["purpose"] == "master"
    assert master_key["status"] == "issued"
    valid_from = datetime.fromisoformat(master_key["valid_from"])
    valid_to = datetime.fromisoformat(master_key["valid_to"])
    assert valid_to - valid_from == timedelta(minutes=10)

    wrong_password = auth_client.post(
        f"/api/digital-keys/cars/{car['id']}/master",
        json={
            "password": "wrong-password",
            "reason": "点検のため",
            "confirm_in_use": False,
        },
    )
    assert wrong_password.status_code == 403

    unlock = auth_client.post(
        f"/api/digital-keys/cars/{car['id']}/remote-unlock",
        json={
            "password": ADMIN_PASSWORD,
            "reason": "閉じ込め対応",
            "confirm_in_use": False,
        },
    )
    assert unlock.status_code == 200
    assert unlock.json()["ok"] is True

    audit = auth_client.get("/api/digital-keys/audit")
    assert audit.status_code == 200
    actions = {event["action"] for event in audit.json()}
    assert {"issue", "schedule", "remote_unlock"} <= actions

    revoked = auth_client.post(f"/api/digital-keys/{master_key['id']}/revoke")
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "revoked"

    past_start = pricing.now_jst() - timedelta(hours=1)
    in_use = create_reservation(
        auth_client, car["id"], member["id"], past_start, hours=2
    )
    assert in_use.status_code == 201

    needs_confirm = auth_client.post(
        f"/api/digital-keys/cars/{car['id']}/master",
        json={
            "password": ADMIN_PASSWORD,
            "reason": "利用中の確認",
            "confirm_in_use": False,
        },
    )
    assert needs_confirm.status_code == 409

    confirmed = auth_client.post(
        f"/api/digital-keys/cars/{car['id']}/master",
        json={
            "password": ADMIN_PASSWORD,
            "reason": "利用中の確認",
            "confirm_in_use": True,
        },
    )
    assert confirmed.status_code == 201
