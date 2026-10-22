import uuid
from datetime import date, timedelta


def test_borrow_book_endpoint_success(client, auth_headers, test_book):
    payload = {
        "book_id": str(test_book.id),
        "due_date": str(date.today() + timedelta(days=14)),
    }
    response = client.post("/api/v1/borrowings", json=payload, headers=auth_headers)
    assert response.status_code == 201
    body = response.json()
    assert body["book_id"] == str(test_book.id)
    assert body["status"] == "ACTIVE"


def test_borrow_book_unauthorized(client, test_book):
    payload = {
        "book_id": str(test_book.id),
        "due_date": str(date.today() + timedelta(days=14)),
    }
    response = client.post("/api/v1/borrowings", json=payload)
    assert response.status_code == 401


def test_return_book_endpoint_success(client, auth_headers, test_book):
    # Önce ödünç al
    borrow_payload = {
        "book_id": str(test_book.id),
        "due_date": str(date.today() + timedelta(days=14)),
    }
    borrow_resp = client.post("/api/v1/borrowings", json=borrow_payload, headers=auth_headers)
    assert borrow_resp.status_code == 201
    borrow_id = borrow_resp.json()["id"]

    # Şimdi iade et
    return_resp = client.patch(f"/api/v1/borrowings/{borrow_id}/return", headers=auth_headers)
    assert return_resp.status_code == 200
    body = return_resp.json()
    assert body["status"] == "RETURNED"
    assert body["return_date"] == str(date.today())


def test_create_reservation_endpoint_success(client, auth_headers, test_book):
    payload = {"book_id": str(test_book.id)}
    response = client.post("/api/v1/reservations", json=payload, headers=auth_headers)
    assert response.status_code == 201
    body = response.json()
    assert body["book_id"] == str(test_book.id)
    assert body["status"] == "PENDING"


def test_create_reservation_duplicate_rejected(client, auth_headers, test_book):
    payload = {"book_id": str(test_book.id)}
    resp1 = client.post("/api/v1/reservations", json=payload, headers=auth_headers)
    assert resp1.status_code == 201

    resp2 = client.post("/api/v1/reservations", json=payload, headers=auth_headers)
    assert resp2.status_code == 400
    assert "bekleyen" in resp2.json()["detail"].lower()


def test_get_my_borrowings_endpoint(client, auth_headers, test_book):
    payload = {
        "book_id": str(test_book.id),
        "due_date": str(date.today() + timedelta(days=14)),
    }
    client.post("/api/v1/borrowings", json=payload, headers=auth_headers)

    response = client.get("/api/v1/borrowings", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) >= 1
    assert body[0]["book_id"] == str(test_book.id)


def test_get_my_reservations_endpoint(client, auth_headers, test_book):
    payload = {"book_id": str(test_book.id)}
    client.post("/api/v1/reservations", json=payload, headers=auth_headers)

    response = client.get("/api/v1/reservations", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) >= 1
    assert body[0]["book_id"] == str(test_book.id)

