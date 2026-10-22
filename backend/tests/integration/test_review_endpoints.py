from datetime import date, timedelta

from app.core.security import create_access_token, hash_password
from app.modules.auth.models import Role, RoleName, User


def _borrow_book_for_user(client, headers, book_id):
    due = (date.today() + timedelta(days=14)).isoformat()
    resp = client.post(
        "/api/v1/borrowings",
        json={"book_id": str(book_id), "due_date": due},
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()


def test_create_review_without_borrowing_rejected(client, auth_headers, test_book):
    """Kullanıcı kitabı daha önce ödünç almadan yorum yapamamalıdır."""
    payload = {
        "book_id": str(test_book.id),
        "rating": 5,
        "comment": "Harika bir kitap.",
    }
    response = client.post("/api/v1/reviews", json=payload, headers=auth_headers)
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "yorumunuz eklenemedi" in detail.lower()
    assert "ödünç almadığınız için" in detail.lower()


def test_create_review_profanity_filter_rejected(client, auth_headers, test_book):
    """Kötü söz veya ifade içeren yorumlar sebepleriyle birlikte reddedilmelidir."""
    _borrow_book_for_user(client, auth_headers, test_book.id)

    payload_word = {
        "book_id": str(test_book.id),
        "rating": 2,
        "comment": "Bence yazar burada çok aptal bir karakter kurgulamış.",
    }
    resp_word = client.post("/api/v1/reviews", json=payload_word, headers=auth_headers)
    assert resp_word.status_code == 400
    detail_word = resp_word.json()["detail"]
    assert "yorumunuz eklenemedi" in detail_word.lower()
    assert "aptal" in detail_word.lower()

    payload_phrase = {
        "book_id": str(test_book.id),
        "rating": 1,
        "comment": "Tamamen zaman kaybı ve berbat bir kitap olmuş.",
    }
    resp_phrase = client.post("/api/v1/reviews", json=payload_phrase, headers=auth_headers)
    assert resp_phrase.status_code == 400
    detail_phrase = resp_phrase.json()["detail"]
    assert "yorumunuz eklenemedi" in detail_phrase.lower()


def test_create_review_success(client, auth_headers, test_book):
    _borrow_book_for_user(client, auth_headers, test_book.id)

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
    assert body["user_full_name"] == "Test User"
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
    _borrow_book_for_user(client, auth_headers, test_book.id)

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
    _borrow_book_for_user(client, auth_headers, test_book.id)

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


def test_user_can_delete_own_review(client, auth_headers, test_book):
    """Kullanıcı kendi attığı yorumu silebilmelidir."""
    _borrow_book_for_user(client, auth_headers, test_book.id)

    create_resp = client.post(
        "/api/v1/reviews",
        json={"book_id": str(test_book.id), "rating": 4, "comment": "Silinecek yorumum"},
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    review_id = create_resp.json()["id"]

    del_resp = client.delete(f"/api/v1/reviews/{review_id}", headers=auth_headers)
    assert del_resp.status_code == 204

    reviews_after = client.get(f"/api/v1/reviews?book_id={test_book.id}").json()
    assert all(r["id"] != review_id for r in reviews_after)


def test_admin_can_delete_other_user_review_and_normal_user_cannot(
    client, db_session, auth_headers, admin_headers, test_book
):
    """Normal kullanıcı başkasının yorumunu silemez (403), ancak ADMIN silebilir (204)."""
    _borrow_book_for_user(client, auth_headers, test_book.id)

    create_resp = client.post(
        "/api/v1/reviews",
        json={"book_id": str(test_book.id), "rating": 5, "comment": "Normal kullanıcının yorumu"},
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    review_id = create_resp.json()["id"]

    # Başka bir normal kullanıcı oluştur
    user_role = db_session.query(Role).filter_by(name=RoleName.USER).first()
    other_user = User(
        email="other@example.com",
        password_hash=hash_password("pass123"),
        first_name="Other",
        last_name="User",
        roles=[user_role],
    )
    db_session.add(other_user)
    db_session.commit()
    db_session.refresh(other_user)
    other_token = create_access_token(
        user_id=other_user.id, email=other_user.email, roles=["USER"]
    )
    other_headers = {"Authorization": f"Bearer {other_token}"}

    # Başka normal kullanıcı silmeye çalışırsa 403 almalı
    forbidden_resp = client.delete(f"/api/v1/reviews/{review_id}", headers=other_headers)
    assert forbidden_resp.status_code == 403

    # Admin kullanıcı silmeye çalışırsa 204 ile başarılı olmalı
    admin_del_resp = client.delete(f"/api/v1/reviews/{review_id}", headers=admin_headers)
    assert admin_del_resp.status_code == 204


def test_react_to_review_thumbs_up_down_and_toggle(
    client, db_session, auth_headers, test_book
):
    """Kullanıcı diğer kullanıcıların yorumuna Beğen (1) / Beğenme (-1) tepkisi bırakabilmelidir."""
    _borrow_book_for_user(client, auth_headers, test_book.id)

    create_resp = client.post(
        "/api/v1/reviews",
        json={"book_id": str(test_book.id), "rating": 5, "comment": "Çok faydalı bir inceleme."},
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    review_id = create_resp.json()["id"]

    # Kullanıcı kendi yorumuna tepki bırakamaz
    self_react = client.post(
        f"/api/v1/reviews/{review_id}/react",
        json={"value": 1},
        headers=auth_headers,
    )
    assert self_react.status_code == 400

    # Başka bir normal kullanıcı oluştur
    user_role = db_session.query(Role).filter_by(name=RoleName.USER).first()
    other_user = User(
        email="reactor@example.com",
        password_hash=hash_password("pass123"),
        first_name="Reactor",
        last_name="User",
        roles=[user_role],
    )
    db_session.add(other_user)
    db_session.commit()
    db_session.refresh(other_user)
    other_token = create_access_token(
        user_id=other_user.id, email=other_user.email, roles=["USER"]
    )
    other_headers = {"Authorization": f"Bearer {other_token}"}

    # 1) Thumbs Up (Beğen: 1)
    like_resp = client.post(
        f"/api/v1/reviews/{review_id}/react",
        json={"value": 1},
        headers=other_headers,
    )
    assert like_resp.status_code == 200
    assert like_resp.json()["likes_count"] == 1
    assert like_resp.json()["dislikes_count"] == 0

    # 2) Thumbs Down'a geçiş (Beğenme: -1)
    dislike_resp = client.post(
        f"/api/v1/reviews/{review_id}/react",
        json={"value": -1},
        headers=other_headers,
    )
    assert dislike_resp.status_code == 200
    assert dislike_resp.json()["likes_count"] == 0
    assert dislike_resp.json()["dislikes_count"] == 1

    # 3) Aynı tepkiye tekrar tıklayınca geri çekme (Toggle off)
    toggle_resp = client.post(
        f"/api/v1/reviews/{review_id}/react",
        json={"value": -1},
        headers=other_headers,
    )
    assert toggle_resp.status_code == 200
    assert toggle_resp.json()["likes_count"] == 0
    assert toggle_resp.json()["dislikes_count"] == 0



