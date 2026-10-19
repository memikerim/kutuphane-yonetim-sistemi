def test_register_endpoint_success(client):
    payload = {
        "email": "integration_user@example.com",
        "password": "securepassword123",
        "first_name": "Mehmet",
        "last_name": "Demir",
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "integration_user@example.com"
    assert "password" not in body
    assert "password_hash" not in body


def test_register_endpoint_duplicate_email(client):
    payload = {
        "email": "duplicate@example.com",
        "password": "securepassword123",
        "first_name": "Ali",
        "last_name": "Veli",
    }
    resp1 = client.post("/api/v1/auth/register", json=payload)
    assert resp1.status_code == 201

    resp2 = client.post("/api/v1/auth/register", json=payload)
    assert resp2.status_code == 400
    assert "zaten kayıtlı" in resp2.json()["detail"]


def test_register_endpoint_validation_error(client):
    # Şifre çok kısa (< 8 karakter)
    payload = {
        "email": "invalid_val@example.com",
        "password": "short",
        "first_name": "Ali",
        "last_name": "Veli",
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422


def test_login_endpoint_success(client):
    reg_payload = {
        "email": "login_user@example.com",
        "password": "securepassword123",
        "first_name": "Ayşe",
        "last_name": "Kaya",
    }
    client.post("/api/v1/auth/register", json=reg_payload)

    login_payload = {
        "email": "login_user@example.com",
        "password": "securepassword123",
    }
    response = client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


def test_login_endpoint_wrong_password(client):
    reg_payload = {
        "email": "wrong_pwd@example.com",
        "password": "securepassword123",
        "first_name": "Fatma",
        "last_name": "Şen",
    }
    client.post("/api/v1/auth/register", json=reg_payload)

    login_payload = {
        "email": "wrong_pwd@example.com",
        "password": "wrongpassword123",
    }
    response = client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 401
    assert "hatalı" in response.json()["detail"].lower()


def test_login_endpoint_non_existing_user(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@example.com", "password": "password123"},
    )
    assert response.status_code == 401


def test_me_endpoint_with_valid_token(client, auth_headers, test_user):
    response = client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == test_user.email
    assert body["id"] == str(test_user.id)


def test_me_endpoint_without_token(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401

