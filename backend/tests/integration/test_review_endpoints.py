import uuid


def test_create_review_success(client, auth_headers, test_book):
    payload = {
        "book_id": str(test_book.id),
        "rating": 5,
        "comment": "Harika bir klasik, kesinlikle okunmalı.",
    }
    response = client.post("/api/v1/reviews", json=payload, headers=auth_headers)
    assert response.status_code == 201
    body = response.json()
    assert body["book_id"] == str(test_book.id)
    assert body["rating"] == 5
    assert body["comment"] == "Harika bir klasik, kesinlikle okunmalı."
    assert "id" in body
    assert "created_at" in body


def test_create_review_rating_validation_fail(client, auth_headers, test_book):
    # Rating 6 olamaz (1-5 arası kuralı)
    payload_high = {
        "book_id": str(test_book.id),
        "rating": 6,
        "comment": "Fazla puan",
    }
    response_high = client.post("/api/v1/reviews", json=payload_high, headers=auth_headers)
    assert response_high.status_code == 422

    # Rating 0 olamaz (1-5 arası kuralı)
    payload_low = {
        "book_id": str(test_book.id),
        "rating": 0,
        "comment": "Sıfır puan",
    }
    response_low = client.post("/api/v1/reviews", json=payload_low, headers=auth_headers)
    assert response_low.status_code == 422


def test_create_review_duplicate_rejected(client, auth_headers, test_book):
    payload = {
        "book_id": str(test_book.id),
        "rating": 4,
        "comment": "İlk yorumum",
    }
    resp1 = client.post("/api/v1/reviews", json=payload, headers=auth_headers)
    assert resp1.status_code == 201

    # Aynı kullanıcı aynı kitaba ikinci kez yorum yapamaz
    payload2 = {
        "book_id": str(test_book.id),
        "rating": 5,
        "comment": "İkinci yorum denemesi",
    }
    resp2 = client.post("/api/v1/reviews", json=payload2, headers=auth_headers)
    assert resp2.status_code == 400
    assert "daha önce yorum yaptınız" in resp2.json()["detail"].lower()


def test_create_review_unauthorized(client, test_book):
    payload = {
        "book_id": str(test_book.id),
        "rating": 5,
        "comment": "Yetkisiz yorum",
    }
    response = client.post("/api/v1/reviews", json=payload)
    assert response.status_code == 401


def test_get_reviews_public(client, auth_headers, test_book):
    # Önce bir yorum ekle
    payload = {
        "book_id": str(test_book.id),
        "rating": 5,
        "comment": "Açık erişim testi",
    }
    client.post("/api/v1/reviews", json=payload, headers=auth_headers)

    # Token OLMADAN herkese açık olarak oku
    response = client.get("/api/v1/reviews")
    assert response.status_code == 200
    body = response.json()
    assert len(body) >= 1

    # Kitap id'ye göre filtrele
    filtered = client.get(f"/api/v1/reviews?book_id={test_book.id}")
    assert filtered.status_code == 200
    assert len(filtered.json()) >= 1

