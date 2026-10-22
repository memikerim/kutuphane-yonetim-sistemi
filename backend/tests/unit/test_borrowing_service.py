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


def test_borrowing_reserved_book_deletes_reservation(db_session, test_user, test_book):
    """Rezerve edilen kitap ödünç alındığında rezerve listesinden silinmelidir."""
    test_book.stock_count = 1
    db_session.commit()

    res = service.create_reservation(db_session, test_user, ReservationCreate(book_id=test_book.id))
    assert res.expires_at is not None
    assert len(service.get_user_reservations(db_session, test_user)) == 1

    service.create_borrowing(
        db_session,
        test_user,
        BorrowingCreate(book_id=test_book.id, due_date=date.today() + timedelta(days=14)),
    )

    # Ödünç alındıktan sonra rezervasyon listesinden silinmiş olmalı
    assert len(service.get_user_reservations(db_session, test_user)) == 0


def test_reserved_stock_blocks_other_users_from_borrowing(db_session, test_user, test_book):
    """Stok 1 iken 1 kullanıcı rezerve etmişse başka kullanıcı ödünç alamaz, sadece rezerve edebilir."""
    test_book.stock_count = 1
    db_session.commit()

    user2 = User(email="user2@example.com", password_hash="h", first_name="U2", last_name="Test")
    user3 = User(email="user3@example.com", password_hash="h", first_name="U3", last_name="Test")
    db_session.add_all([user2, user3])
    db_session.commit()

    # User 1 rezerve eder (1. sıra, stok=1 olduğu için hak onda)
    res1 = service.create_reservation(db_session, test_user, ReservationCreate(book_id=test_book.id))
    assert res1.queue_position == 1
    assert res1.can_borrow_now is True

    # User 2 doğrudan ödünç almaya çalışırsa reddedilir
    with pytest.raises(service.BusinessRuleError) as exc_info:
        service.create_borrowing(
            db_session,
            user2,
            BorrowingCreate(book_id=test_book.id, due_date=date.today() + timedelta(days=14)),
        )
    assert "rezerve" in str(exc_info.value).lower()

    # Ancak User 2 ve User 3 rezerve ederek sıraya girebilir
    res2 = service.create_reservation(db_session, user2, ReservationCreate(book_id=test_book.id))
    res3 = service.create_reservation(db_session, user3, ReservationCreate(book_id=test_book.id))
    assert res2.queue_position == 2
    assert res3.queue_position == 3
    assert "3. sıradasınız" in res3.queue_message


def test_reservation_24h_timer_starts_on_stock_and_expires_to_next_user(db_session, test_user, test_book):
    """Stok 0 iken süre başlamaz; stok açılınca 24 saat süre başlar, süre dolunca silinip sıradakine geçer."""
    from datetime import datetime, timezone

    test_book.stock_count = 0
    db_session.commit()

    user2 = User(email="queue2@example.com", password_hash="h", first_name="Q2", last_name="Test")
    db_session.add(user2)
    db_session.commit()

    res1 = service.create_reservation(db_session, test_user, ReservationCreate(book_id=test_book.id))
    res2 = service.create_reservation(db_session, user2, ReservationCreate(book_id=test_book.id))

    # Stok 0 olduğu için henüz kimsenin 24 saatlik süresi başlamadı
    assert res1.expires_at is None
    assert res2.expires_at is None

    # Stok 1'e çıkarıldığında 1. sıradaki kullanıcının 24 saatlik süresi başlar
    test_book.stock_count = 1
    db_session.commit()
    service.sync_reservations(db_session, test_book.id)
    db_session.refresh(res1)
    db_session.refresh(res2)

    assert res1.expires_at is not None
    assert res1.can_borrow_now is True
    assert res2.expires_at is None

    # 1. kullanıcının 24 saatlik süresi dolduğunda rezerveden silinir ve sıra 2. kullanıcıya geçer
    res1.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    db_session.commit()

    user1_list = service.get_user_reservations(db_session, test_user)
    user2_list = service.get_user_reservations(db_session, user2)

    assert len(user1_list) == 0
    assert len(user2_list) == 1
    assert user2_list[0].queue_position == 1
    assert user2_list[0].can_borrow_now is True
    assert user2_list[0].expires_at is not None


def test_overdue_simulation_and_penalty_calculation_on_return(db_session, test_user, test_book):
    """Gecikme simülasyonu (-5 gün) sonrası iade edildiğinde 5 * 10.0 = 50.0 TL ceza oluşmalı."""
    borrowing = service.create_borrowing(
        db_session,
        test_user,
        BorrowingCreate(book_id=test_book.id, due_date=date.today() + timedelta(days=14)),
    )

    sim = service.simulate_overdue_borrowing(db_session, borrowing.id)
    assert sim.status == BorrowingStatus.OVERDUE
    assert sim.due_date == date.today() - timedelta(days=5)
    assert sim.overdue_days == 5

    returned = service.return_borrowing(db_session, test_user, borrowing.id)
    assert returned.status == BorrowingStatus.RETURNED
    assert returned.penalty_amount == 50.0
    assert returned.is_penalty_paid is False


def test_overdue_or_unpaid_penalty_blocks_new_borrowing_and_reservation(db_session, test_user, test_book):
    """Gecikmiş kitabı veya ödenmemiş cezası olan kullanıcı yeni ödünç ve rezervasyon yapamaz; ödeyince açılır."""
    from app.modules.catalog.models import Book

    book2 = Book(
        title="İkinci Kitap",
        isbn="9789750509999",
        published_year=2020,
        stock_count=3,
    )
    db_session.add(book2)
    db_session.commit()

    b1 = service.create_borrowing(
        db_session,
        test_user,
        BorrowingCreate(book_id=test_book.id, due_date=date.today() + timedelta(days=7)),
    )
    service.simulate_overdue_borrowing(db_session, b1.id)

    # 1. Aktif OVERDUE kitap varken yeni ödünç ve rezervasyon engellenmeli
    with pytest.raises(service.BusinessRuleError) as exc_borrow:
        service.create_borrowing(
            db_session,
            test_user,
            BorrowingCreate(book_id=book2.id, due_date=date.today() + timedelta(days=7)),
        )
    assert "ödenmemiş gecikme cezanız veya süresi geçmiş kitabınız" in str(exc_borrow.value).lower()

    with pytest.raises(service.BusinessRuleError) as exc_res:
        service.create_reservation(db_session, test_user, ReservationCreate(book_id=book2.id))
    assert "ödenmemiş gecikme cezanız veya süresi geçmiş kitabınız" in str(exc_res.value).lower()

    # 2. Kitap iade edildiğinde 50 TL ödenmemiş ceza oluşur -> hala engellenmeli
    service.return_borrowing(db_session, test_user, b1.id)

    with pytest.raises(service.BusinessRuleError) as exc_unpaid:
        service.create_borrowing(
            db_session,
            test_user,
            BorrowingCreate(book_id=book2.id, due_date=date.today() + timedelta(days=7)),
        )
    assert "ödenmemiş gecikme cezanız" in str(exc_unpaid.value).lower()

    # 3. Ceza ödendiğinde blokaj kalkmalı
    paid = service.pay_borrowing_penalty(db_session, test_user, b1.id)
    assert paid.is_penalty_paid is True

    b2 = service.create_borrowing(
        db_session,
        test_user,
        BorrowingCreate(book_id=book2.id, due_date=date.today() + timedelta(days=7)),
    )
    assert b2.status == BorrowingStatus.ACTIVE


