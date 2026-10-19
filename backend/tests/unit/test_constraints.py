"""Tüm veritabanı seviyesi kısıtlamaların (CHECK, UNIQUE, PARTIAL UNIQUE) ve Pydantic şema sınırlarının doğrudan testleri."""

from datetime import date, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.modules.auth.models import User
from app.modules.borrowing.models import Borrowing, BorrowingStatus, Reservation, ReservationStatus
from app.modules.catalog.models import Book, Category
from app.modules.catalog.schemas import BookCreate, BookUpdate
from app.modules.review.models import Review
from app.modules.review.schemas import ReviewCreate


# =====================================================================
# 1. STOK SAYISI NEGATİF OLAMAZ KISITLAMASI (stock_count >= 0)
# =====================================================================
def test_db_constraint_book_negative_stock_rejected(db_session):
    """Veritabanı seviyesinde stock_count = -1 girildiğinde CheckConstraint (stock_count >= 0) patlamalı."""
    book = Book(
        title="Negatif Stok Test Kitabı",
        isbn="9780000000999",
        published_year=2024,
        stock_count=-1,  # Kural ihlali!
    )
    db_session.add(book)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_pydantic_book_create_negative_stock_rejected():
    """Pydantic şemasında (BookCreate) stock_count = -1 girildiğinde ValidationError fırlatmalı."""
    with pytest.raises(ValidationError):
        BookCreate(
            title="Test Kitap",
            isbn="9781234567890",
            stock_count=-1,
        )


def test_pydantic_book_update_negative_stock_rejected():
    """Pydantic güncelleme şemasında (BookUpdate) stock_count = -5 girildiğinde ValidationError fırlatmalı."""
    with pytest.raises(ValidationError):
        BookUpdate(stock_count=-5)


def test_api_create_book_negative_stock_rejected(client, admin_headers):
    """API üzerinden (POST /api/v1/books) stock_count: -1 gönderildiğinde 422 Unprocessable Entity dönmeli."""
    payload = {
        "title": "Negatif Stok API Test",
        "isbn": "9781112223334",
        "published_year": 2024,
        "stock_count": -1,
    }
    response = client.post("/api/v1/books", json=payload, headers=admin_headers)
    assert response.status_code == 422


def test_api_borrow_book_when_stock_is_zero_rejected(client, auth_headers, db_session, test_book):
    """Kitap stoku 0 iken API üzerinden ödünç alınmaya çalışıldığında stok -1'e düşemez ve 400 Bad Request döner."""
    test_book.stock_count = 0
    db_session.commit()

    payload = {
        "book_id": str(test_book.id),
        "due_date": str(date.today() + timedelta(days=7)),
    }
    response = client.post("/api/v1/borrowings", json=payload, headers=auth_headers)
    assert response.status_code == 400
    assert "stokta yok" in response.json()["detail"].lower()


# =====================================================================
# 2. PUAN (RATING) 1-5 ARASI OLMA KISITLAMASI (rating BETWEEN 1 AND 5)
# =====================================================================
@pytest.mark.parametrize("invalid_rating", [-1, 0, 6, 100])
def test_db_constraint_review_rating_out_of_range_rejected(db_session, test_user, test_book, invalid_rating):
    """Veritabanına doğrudan 1-5 dışı (-1, 0, 6, 100) puan yazılmaya çalışıldığında CheckConstraint engellemeli."""
    review = Review(
        user_id=test_user.id,
        book_id=test_book.id,
        rating=invalid_rating,
        comment="Geçersiz puan testi",
    )
    db_session.add(review)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


@pytest.mark.parametrize("invalid_rating", [-5, -1, 0, 6, 10])
def test_pydantic_review_rating_out_of_range_rejected(test_book, invalid_rating):
    """Pydantic ReviewCreate şemasında 1-5 dışı puanlar reddedilmeli."""
    with pytest.raises(ValidationError):
        ReviewCreate(
            book_id=test_book.id,
            rating=invalid_rating,
            comment="Test",
        )


# =====================================================================
# 3. ÖDÜNÇ ALMA TARİH KISITLAMALARI (due_date >= borrow_date, return_date >= borrow_date)
# =====================================================================
def test_db_constraint_borrowing_due_before_borrow_rejected(db_session, test_user, test_book):
    """Veritabanında due_date < borrow_date olduğunda CheckConstraint (due_after_borrow) engellemeli."""
    borrowing = Borrowing(
        user_id=test_user.id,
        book_id=test_book.id,
        borrow_date=date(2026, 10, 20),
        due_date=date(2026, 10, 10),  # Ödünç tarihinden önce!
        status=BorrowingStatus.ACTIVE,
    )
    db_session.add(borrowing)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_db_constraint_borrowing_return_before_borrow_rejected(db_session, test_user, test_book):
    """Veritabanında return_date < borrow_date olduğunda CheckConstraint (return_after_borrow) engellemeli."""
    borrowing = Borrowing(
        user_id=test_user.id,
        book_id=test_book.id,
        borrow_date=date(2026, 10, 20),
        due_date=date(2026, 10, 30),
        return_date=date(2026, 10, 15),  # Ödünç tarihinden önce iade!
        status=BorrowingStatus.RETURNED,
    )
    db_session.add(borrowing)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# =====================================================================
# 4. TEKİLLİK (UNIQUE) KISITLAMALARI (ISBN, Category, Email, Review, Reservation)
# =====================================================================
def test_db_constraint_duplicate_isbn_rejected(db_session, test_book):
    """Aynı ISBN ile ikinci bir kitap eklenemez (UniqueConstraint)."""
    duplicate_book = Book(
        title="Farklı Başlık Ama Aynı ISBN",
        isbn=test_book.isbn,
        stock_count=3,
    )
    db_session.add(duplicate_book)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_db_constraint_duplicate_category_name_rejected(db_session):
    """Aynı isimle ikinci bir kategori eklenemez (UniqueConstraint)."""
    cat1 = Category(name="Bilim Kurgu")
    db_session.add(cat1)
    db_session.commit()

    cat2 = Category(name="Bilim Kurgu")
    db_session.add(cat2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_db_constraint_duplicate_user_email_rejected(db_session, test_user):
    """Aynı e-posta ile ikinci bir kullanıcı doğrudan DB'ye eklenemez."""
    dup_user = User(
        email=test_user.email,
        password_hash="hash",
        first_name="Dup",
        last_name="User",
    )
    db_session.add(dup_user)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_db_constraint_duplicate_review_user_book_rejected(db_session, test_user, test_book):
    """Aynı kullanıcı aynı kitaba DB seviyesinde ikinci yorumu ekleyemez (uq_reviews_user_book)."""
    r1 = Review(user_id=test_user.id, book_id=test_book.id, rating=4, comment="İlk")
    db_session.add(r1)
    db_session.commit()

    r2 = Review(user_id=test_user.id, book_id=test_book.id, rating=5, comment="İkinci")
    db_session.add(r2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_db_constraint_duplicate_pending_reservation_rejected(db_session, test_user, test_book):
    """Aynı kullanıcı aynı kitaba DB seviyesinde ikinci PENDING rezervasyonu ekleyemez (uq_reservations_user_book_pending)."""
    res1 = Reservation(user_id=test_user.id, book_id=test_book.id, status=ReservationStatus.PENDING)
    db_session.add(res1)
    db_session.commit()

    res2 = Reservation(user_id=test_user.id, book_id=test_book.id, status=ReservationStatus.PENDING)
    db_session.add(res2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

