def test_health_is_public(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_page_is_public(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "予約アプリ" in response.text


def test_api_requires_login(client):
    response = client.get("/api/cars/")
    assert response.status_code == 401


def test_login_with_wrong_password(client):
    response = client.post(
        "/api/auth/login", json={"password": "wrong-password"}
    )
    assert response.status_code == 401
    assert client.get("/api/auth/me").status_code == 401


def test_login_with_non_ascii_password(client):
    response = client.post(
        "/api/auth/login", json={"password": "日本語のパスワード"}
    )
    assert response.status_code == 401


def test_login_with_empty_password(client):
    response = client.post("/api/auth/login", json={"password": ""})
    assert response.status_code == 422


def test_login_and_logout(client):
    response = client.post(
        "/api/auth/login", json={"password": "test-password"}
    )
    assert response.status_code == 200
    assert response.json() == {"authenticated": True}
    assert client.cookies.get("reservation_session")

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json() == {"authenticated": True}

    logout = client.post("/api/auth/logout")
    assert logout.status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_login_rate_limit(client):
    for _ in range(5):
        response = client.post(
            "/api/auth/login", json={"password": "wrong-password"}
        )
        assert response.status_code == 401

    blocked = client.post(
        "/api/auth/login", json={"password": "wrong-password"}
    )
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers
