import uuid
from datetime import date, timedelta

import pytest

from app.modules.auth.models import Role, RoleName, User
from app.modules.borrowing import service
from app.modules.borrowing.models import BorrowingStatus, ReservationStatus
from app.modules.borrowing.schemas import BorrowingCreate, ReservationCreate


def test_create_borrowing_success(db_session, test_user, test_book):
    initial_stock = test_book.stock_count
    data = BorrowingCreate(
        book_id=test_book.id,
        due_date=date.today() + timedelta(days=14),
    )
    borrowing = service.create_borrowing(db_session, test_user, data)

    assert borrowing.id is not None
    assert borrowing.user_id == test_user.id
    assert borrowing.book_id == test_book.id
    assert borrowing.status == BorrowingStatus.ACTIVE
    db_session.refresh(test_book)
    assert test_book.stock_count == initial_stock - 1


def test_create_borrowing_zero_stock_rejected(db_session, test_user, test_book):
    """Stok 0 olduğunda ödünç alma işlemi veritabanı kısıtlamasıyla reddedilmeli (negatif olamaz)."""
    test_book.stock_count = 0
    db_session.commit()

    data = BorrowingCreate(
        book_id=test_book.id,
        due_date=date.today() + timedelta(days=14),
    )
    with pytest.raises(service.BusinessRuleError) as exc_info:
        service.create_borrowing(db_session, test_user, data)
    assert "stokta yok" in str(exc_info.value).lower()


def test_create_borrowing_past_due_date(db_session, test_user, test_book):
    data = BorrowingCreate(
        book_id=test_book.id,
        due_date=date.today() - timedelta(days=1),
    )
    with pytest.raises(service.BusinessRuleError) as exc_info:
        service.create_borrowing(db_session, test_user, data)
    assert "geçmiş bir tarih olamaz" in str(exc_info.value)


def test_create_borrowing_book_not_found(db_session, test_user):
    data = BorrowingCreate(
        book_id=uuid.uuid4(),
        due_date=date.today() + timedelta(days=7),
    )
    with pytest.raises(service.NotFoundError):
        service.create_borrowing(db_session, test_user, data)


def test_create_borrowing_duplicate_active_same_book_rejected(db_session, test_user, test_book):
    """Kullanıcı elinde aktif (iade edilmemiş) bir kitap varken aynı kitabı ikinci kez ödünç alamaz."""
    data = BorrowingCreate(
        book_id=test_book.id,
        due_date=date.today() + timedelta(days=14),
    )
    service.create_borrowing(db_session, test_user, data)

    with pytest.raises(service.BusinessRuleError) as exc_info:
        service.create_borrowing(db_session, test_user, data)
    assert "zaten şu an üzerinizde" in str(exc_info.value).lower()


def test_create_borrowing_same_book_allowed_after_return(db_session, test_user, test_book):
    """Kullanıcı kitabı iade ettikten (RETURNED) sonra aynı kitabı tekrar ödünç alabilmelidir."""
    data = BorrowingCreate(
        book_id=test_book.id,
        due_date=date.today() + timedelta(days=14),
    )
    b1 = service.create_borrowing(db_session, test_user, data)
    service.return_borrowing(db_session, test_user, b1.id)

    b2 = service.create_borrowing(db_session, test_user, data)
    assert b2.id != b1.id
    assert b2.status == BorrowingStatus.ACTIVE


def test_create_borrowing_max_three_active_books_quota_rejected(db_session, test_user):
    """Bir kullanıcı aynı anda en fazla 3 adet aktif ödünç kitaba sahip olabilir (4. kitap reddedilir)."""
    from app.modules.catalog.models import Book

    books = []
    for i in range(4):
        b = Book(
            title=f"Kota Test Kitap {i+1}",
            isbn=f"978000000100{i}",
            published_year=2024,
            stock_count=5,
        )
        db_session.add(b)
        books.append(b)
    db_session.commit()

    # İlk 3 kitap başarıyla ödünç alınır
    for i in range(3):
        service.create_borrowing(
            db_session,
            test_user,
            BorrowingCreate(book_id=books[i].id, due_date=date.today() + timedelta(days=14)),
        )

    # 4. kitap ödünç alınmak istendiğinde kota hatası fırlatılır
    with pytest.raises(service.BusinessRuleError) as exc_info:
        service.create_borrowing(
            db_session,
            test_user,
            BorrowingCreate(book_id=books[3].id, due_date=date.today() + timedelta(days=14)),
        )
    assert "en fazla 3 adet" in str(exc_info.value).lower()


def test_return_borrowing_success(db_session, test_user, test_book):
    data = BorrowingCreate(
        book_id=test_book.id,
        due_date=date.today() + timedelta(days=14),
    )
    borrowing = service.create_borrowing(db_session, test_user, data)
    stock_after_borrow = test_book.stock_count

    returned = service.return_borrowing(db_session, test_user, borrowing.id)
    assert returned.status == BorrowingStatus.RETURNED
    assert returned.return_date == date.today()
    db_session.refresh(test_book)
    assert test_book.stock_count == stock_after_borrow + 1


def test_return_borrowing_not_owner(db_session, test_user, test_book):
    data = BorrowingCreate(
        book_id=test_book.id,
        due_date=date.today() + timedelta(days=14),
    )
    borrowing = service.create_borrowing(db_session, test_user, data)

    # Başka bir kullanıcı
    other_user = User(
        email="baskasi@example.com",
        password_hash="hash",
        first_name="Baska",
        last_name="Kullanici",
    )
    db_session.add(other_user)
    db_session.commit()

    with pytest.raises(service.BusinessRuleError) as exc_info:
        service.return_borrowing(db_session, other_user, borrowing.id)
    assert "size ait değil" in str(exc_info.value)


def test_return_borrowing_already_returned(db_session, test_user, test_book):
    data = BorrowingCreate(
        book_id=test_book.id,
        due_date=date.today() + timedelta(days=14),
    )
    borrowing = service.create_borrowing(db_session, test_user, data)
    service.return_borrowing(db_session, test_user, borrowing.id)

    with pytest.raises(service.BusinessRuleError) as exc_info:
        service.return_borrowing(db_session, test_user, borrowing.id)
    assert "zaten iade edilmiş" in str(exc_info.value)


def test_create_reservation_success(db_session, test_user, test_book):
    data = ReservationCreate(book_id=test_book.id)
    reservation = service.create_reservation(db_session, test_user, data)

    assert reservation.id is not None
    assert reservation.user_id == test_user.id
    assert reservation.book_id == test_book.id
    assert reservation.status == ReservationStatus.PENDING


def test_create_reservation_duplicate_pending_rejected(db_session, test_user, test_book):
    """Aynı kullanıcı aynı kitaba PENDING rezervasyonu varken tekrar rezervasyon yapamaz."""
    data = ReservationCreate(book_id=test_book.id)
    service.create_reservation(db_session, test_user, data)

    with pytest.raises(service.BusinessRuleError) as exc_info:
        service.create_reservation(db_session, test_user, data)
    assert "bekleyen" in str(exc_info.value).lower()


def test_create_reservation_allowed_after_cancelled(db_session, test_user, test_book):
    """Partial unique index testi: Eski rezervasyon CANCELLED ise yeni PENDING oluşturulabilmeli."""
    data = ReservationCreate(book_id=test_book.id)
    res1 = service.create_reservation(db_session, test_user, data)
    res1.status = ReservationStatus.CANCELLED
    db_session.commit()

    res2 = service.create_reservation(db_session, test_user, data)
    assert res2.id != res1.id
    assert res2.status == ReservationStatus.PENDING


def test_create_reservation_book_not_found(db_session, test_user):
    data = ReservationCreate(book_id=uuid.uuid4())
    with pytest.raises(service.NotFoundError):
        service.create_reservation(db_session, test_user, data)


def test_get_user_reservations_ordered(db_session, test_user, test_book):
    data = ReservationCreate(book_id=test_book.id)
    service.create_reservation(db_session, test_user, data)

    reservations = service.get_user_reservations(db_session, test_user)
    assert len(reservations) >= 1
    assert reservations[0].book_id == test_book.id
