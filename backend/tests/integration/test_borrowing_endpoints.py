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


def test_simulate_overdue_and_pay_penalty_flow_endpoints(
    client, auth_headers, admin_headers, test_book, db_session
):
    from app.modules.catalog.models import Book

    book2 = Book(
        title="Ceza Test Kitabı",
        isbn="9789750508888",
        published_year=2022,
        stock_count=2,
    )
    db_session.add(book2)
    db_session.commit()

    # 1. Kullanıcı kitabı ödünç alır
    borrow_resp = client.post(
        "/api/v1/borrowings",
        json={"book_id": str(test_book.id), "due_date": str(date.today() + timedelta(days=10))},
        headers=auth_headers,
    )
    assert borrow_resp.status_code == 201
    borrow_id = borrow_resp.json()["id"]

    # 2. Normal kullanıcı simulate-overdue çağırırsa 403 almalı
    forbidden_resp = client.patch(
        f"/api/v1/admin/borrowings/{borrow_id}/simulate-overdue",
        headers=auth_headers,
    )
    assert forbidden_resp.status_code == 403

    # 3. Admin simulate-overdue çağırırsa 200 ve 5 gün gecikme (50 TL dinamik ceza) dönmeli
    sim_resp = client.patch(
        f"/api/v1/admin/borrowings/{borrow_id}/simulate-overdue",
        headers=admin_headers,
    )
    assert sim_resp.status_code == 200
    sim_body = sim_resp.json()
    assert sim_body["status"] == "OVERDUE"
    assert sim_body["overdue_days"] == 5
    assert sim_body["penalty_amount"] == 50.0

    # 4. Gecikmiş kitap varken yeni ödünç veya rezervasyon 400 ile reddedilmeli
    blocked_borrow = client.post(
        "/api/v1/borrowings",
        json={"book_id": str(book2.id), "due_date": str(date.today() + timedelta(days=10))},
        headers=auth_headers,
    )
    assert blocked_borrow.status_code == 400
    assert "ödenmemiş gecikme cezanız veya süresi geçmiş kitabınız" in blocked_borrow.json()["detail"].lower()

    blocked_res = client.post(
        "/api/v1/reservations",
        json={"book_id": str(book2.id)},
        headers=auth_headers,
    )
    assert blocked_res.status_code == 400

    # 5. Kitap iade edilir -> 50 TL ceza kesinleşir (is_penalty_paid = False)
    ret_resp = client.patch(f"/api/v1/borrowings/{borrow_id}/return", headers=auth_headers)
    assert ret_resp.status_code == 200
    ret_body = ret_resp.json()
    assert ret_body["status"] == "RETURNED"
    assert ret_body["penalty_amount"] == 50.0
    assert ret_body["is_penalty_paid"] is False

    # 6. Ceza ödenmeden yeni ödünç hala 400 dönmeli
    still_blocked = client.post(
        "/api/v1/borrowings",
        json={"book_id": str(book2.id), "due_date": str(date.today() + timedelta(days=10))},
        headers=auth_headers,
    )
    assert still_blocked.status_code == 400

    # 7. Ceza ödenir -> POST /api/v1/borrowings/{id}/pay-penalty
    pay_resp = client.post(f"/api/v1/borrowings/{borrow_id}/pay-penalty", headers=auth_headers)
    assert pay_resp.status_code == 200
    assert pay_resp.json()["is_penalty_paid"] is True

    # 8. Artık yeni kitap ödünç alınabilir
    ok_borrow = client.post(
        "/api/v1/borrowings",
        json={"book_id": str(book2.id), "due_date": str(date.today() + timedelta(days=10))},
        headers=auth_headers,
    )
    assert ok_borrow.status_code == 201


