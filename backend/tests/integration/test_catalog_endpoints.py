from unittest.mock import MagicMock, patch
import uuid


def test_create_and_get_book_with_cover_url(client, admin_headers):
    # 1. Yayınevi oluştur
    pub_res = client.post(
        "/api/v1/publishers",
        json={"name": "Can Yayınları", "contact_info": "info@canyayinlari.com"},
        headers=admin_headers,
    )
    assert pub_res.status_code == 201
    pub_id = pub_res.json()["id"]

    # 2. Yazar oluştur
    auth_res = client.post(
        "/api/v1/authors",
        json={"first_name": "Albert", "last_name": "Camus"},
        headers=admin_headers,
    )
    assert auth_res.status_code == 201
    author_id = auth_res.json()["id"]

    # 3. Kategori oluştur
    cat_res = client.post(
        "/api/v1/categories",
        json={"name": "Felsefe"},
        headers=admin_headers,
    )
    assert cat_res.status_code == 201
    cat_id = cat_res.json()["id"]

    # 4. Kitap oluştur (cover_url ile)
    cover = "https://covers.openlibrary.org/b/id/12345-L.jpg"
    book_payload = {
        "title": "Yabancı",
        "isbn": "9789750719387",
        "published_year": 1942,
        "stock_count": 5,
        "publisher_id": pub_id,
        "author_ids": [author_id],
        "category_ids": [cat_id],
        "cover_url": cover,
    }
    create_res = client.post("/api/v1/books", json=book_payload, headers=admin_headers)
    assert create_res.status_code == 201
    created_book = create_res.json()
    assert created_book["cover_url"] == cover
    assert created_book["title"] == "Yabancı"
    book_id = created_book["id"]

    # 5. Kitap detayını oku
    get_res = client.get(f"/api/v1/books/{book_id}")
    assert get_res.status_code == 200
    assert get_res.json()["cover_url"] == cover


def test_lookup_isbn_unauthorized_and_forbidden(client, auth_headers):
    isbn = "9780140328721"

    # Token olmadan -> 401
    no_token_res = client.get(f"/api/v1/books/lookup-isbn/{isbn}")
    assert no_token_res.status_code == 401

    # Normal kullanıcı (USER rolü) -> 403
    forbidden_res = client.get(f"/api/v1/books/lookup-isbn/{isbn}", headers=auth_headers)
    assert forbidden_res.status_code == 403


def test_lookup_isbn_success_with_auto_creation(client, admin_headers):
    isbn = "9780140328721"
    mock_ol_response = {
        f"ISBN:{isbn}": {
            "title": "Fantastic Mr. Fox",
            "publish_date": "October 1, 1988",
            "cover": {
                "large": "https://covers.openlibrary.org/b/id/15152634-L.jpg",
                "medium": "https://covers.openlibrary.org/b/id/15152634-M.jpg",
            },
            "authors": [{"name": "Roald Dahl"}],
            "publishers": [{"name": "Puffin Books"}],
            "subjects": [{"name": "Animals"}, {"name": "Children's Fiction"}],
        }
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_ol_response

    mock_client_instance = MagicMock()
    mock_client_instance.get.return_value = mock_resp
    mock_client_instance.__enter__.return_value = mock_client_instance

    with patch("app.modules.catalog.service.httpx.Client", return_value=mock_client_instance):
        res = client.get(f"/api/v1/books/lookup-isbn/{isbn}", headers=admin_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["title"] == "Fantastic Mr. Fox"
        assert data["isbn"] == isbn
        assert data["published_year"] == 1988
        assert data["cover_url"] == "https://covers.openlibrary.org/b/id/15152634-L.jpg"
        assert data["publisher_id"] is not None
        assert data["publisher_name"] == "Puffin Books"
        assert len(data["author_ids"]) == 1
        assert "Roald Dahl" in data["author_names"]
        assert len(data["category_ids"]) >= 1

        # Veritabanında yayınevi, yazar ve kategorinin oluştuğunu doğrula
        pub_res = client.get(f"/api/v1/publishers/{data['publisher_id']}")
        assert pub_res.status_code == 200
        assert pub_res.json()["name"] == "Puffin Books"

        auth_res = client.get(f"/api/v1/authors/{data['author_ids'][0]}")
        assert auth_res.status_code == 200
        assert auth_res.json()["first_name"] == "Roald"
        assert auth_res.json()["last_name"] == "Dahl"


def test_lookup_isbn_not_found(client, admin_headers):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {}  # Boş sonuç

    mock_client_instance = MagicMock()
    mock_client_instance.get.return_value = mock_resp
    mock_client_instance.__enter__.return_value = mock_client_instance

    with patch("app.modules.catalog.service.httpx.Client", return_value=mock_client_instance):
        res = client.get("/api/v1/books/lookup-isbn/9999999999999", headers=admin_headers)
        assert res.status_code == 404
        assert "bulunamadı" in res.json()["detail"].lower()
