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


def test_reservation_timer_starts_without_user_login_and_cascades_accurately(db_session, test_user, test_book):
    """
    1. Kitap iade edilip stoğa girdiği anda 1. sıradaki kullanıcının 24 saatlik sayacı
       kullanıcının giriş yapmasını beklemeden anında başlamalı.
    2. 1. sıradaki kullanıcının süresi dolduğunda (örn. 6 saat önce dolmuşsa),
       2. sıradaki kullanıcının 24 saatlik sayacı giriş yaptığı andan (24 saat) değil,
       1. kullanıcının süresinin bittiği andan itibaren başlamış olmalı (18 saat kalmalı).
    3. Aradan 30 saat geçmişse hem 1. hem 2. kullanıcının 24 saatlik hakkı dolmuş olmalı
       ve sıra 3. kullanıcıya (18 saat kalan süreyle) geçmiş olmalı.
    """
    from datetime import datetime, timezone

    test_book.stock_count = 1
    db_session.commit()

    user2 = User(email="cascade2@example.com", password_hash="h", first_name="C2", last_name="Test")
    user3 = User(email="cascade3@example.com", password_hash="h", first_name="C3", last_name="Test")
    user4 = User(email="cascade4@example.com", password_hash="h", first_name="C4", last_name="Test")
    db_session.add_all([user2, user3, user4])
    db_session.commit()

    # test_user kitabı ödünç alır -> stok 0 olur
    b = service.create_borrowing(
        db_session,
        test_user,
        BorrowingCreate(book_id=test_book.id, due_date=date.today() + timedelta(days=14)),
    )
    db_session.refresh(test_book)
    assert test_book.stock_count == 0

    # user2, user3 ve user4 sırayla rezerve eder (stok 0 iken kimsenin sayacı başlamaz)
    res2 = service.create_reservation(db_session, user2, ReservationCreate(book_id=test_book.id))
    res3 = service.create_reservation(db_session, user3, ReservationCreate(book_id=test_book.id))
    res4 = service.create_reservation(db_session, user4, ReservationCreate(book_id=test_book.id))
    assert res2.expires_at is None
    assert res3.expires_at is None
    assert res4.expires_at is None

    # test_user kitabı iade ettiği anda user2 hiç giriş yapmasa bile user2'nin 24 saatlik sayacı başlamış olmalı!
    service.return_borrowing(db_session, test_user, b.id)
    db_session.refresh(res2)
    db_session.refresh(res3)
    assert res2.expires_at is not None
    assert res3.expires_at is None
    assert res3.turn_starts_at is not None

    # Senaryo A: user2'nin 24 saatlik süresi 6 saat önce dolmuş olsun ve kimse giriş yapmamış olsun.
    # Şimdi sistem kontrol edildiğinde user3'ün süresi 6 saat önce başlamış olmalı (yaklaşık 18 saat kalmalı, 24 saat değil!)
    now = datetime.now(timezone.utc)
    res2.expires_at = now - timedelta(hours=6)
    db_session.commit()

    service.sync_reservations(db_session, test_book.id)
    db_session.refresh(res3)
    db_session.refresh(res4)

    assert res3.queue_position == 1
    assert res3.can_borrow_now is True
    assert res3.expires_at is not None
    # Kalan süre 24 saat (86400 sn) değil, 18 saat (~64800 sn) civarında olmalı
    assert 17 * 3600 <= res3.remaining_seconds <= 18 * 3600 + 60

    # Senaryo B: user3'ün de süresi 2 saat önce dolmuş olsun -> sıra otomatik olarak user4'e geçmeli (22 saat kalmalı)
    res3.expires_at = datetime.now(timezone.utc) - timedelta(hours=2)
    db_session.commit()

    user4_reservations = service.get_user_reservations(db_session, user4)
    assert len(user4_reservations) == 1
    assert user4_reservations[0].queue_position == 1
    assert user4_reservations[0].can_borrow_now is True
    assert 21 * 3600 <= user4_reservations[0].remaining_seconds <= 22 * 3600 + 60


def test_approval_workflow_and_damaged_lost_stock_history(db_session, test_user, admin_user, test_book):
    from app.modules.borrowing.schemas import (
        AdminApproveReturnRequest,
        BorrowingReturn,
        StockMovementCreate,
    )

    test_book.stock_count = 3
    db_session.commit()

    # 1. Kullanıcı onay kuyruğuna düşen ödünç talebi oluşturur (PENDING_BORROW)
    borrow_req = service.create_borrowing(
        db_session,
        test_user,
        BorrowingCreate(
            book_id=test_book.id,
            due_date=date.today() + timedelta(days=14),
            request_approval=True,
            notes="Sınav hazırlığı için ödünç talep ediyorum",
        ),
    )
    assert borrow_req.approval_status == "PENDING_BORROW"
    db_session.refresh(test_book)
    assert test_book.stock_count == 2  # Stok ayrıldı (-1)

    # 2. Admin ödünç talebini onaylar -> APPROVED
    approved = service.admin_approve_borrow(
        db_session, admin_user, borrow_req.id, admin_notes="Kimlik kontrolü yapıldı ve teslim edildi"
    )
    assert approved.approval_status == "APPROVED"
    assert approved.status == BorrowingStatus.ACTIVE

    # 3. Kullanıcı kitabı hasarlı olarak iade talebine gönderir (PENDING_RETURN)
    ret_req = service.return_borrowing(
        db_session,
        test_user,
        borrow_req.id,
        BorrowingReturn(
            request_approval=True,
            return_condition="DAMAGED",
            return_notes="Su dökülmesi nedeniyle arka kapak hasar gördü",
        ),
    )
    assert ret_req.approval_status == "PENDING_RETURN"
    assert ret_req.return_condition == "DAMAGED"
    db_session.refresh(test_book)
    assert test_book.stock_count == 2  # Henüz onaylanmadığı için stok değişmedi

    # 4. Admin fiziksel kontrolü yapar ve hasarlı iadeyi onaylar (100 TL tazminat + stoktan düşüm)
    final_ret = service.admin_approve_return(
        db_session,
        admin_user,
        borrow_req.id,
        AdminApproveReturnRequest(
            return_condition="DAMAGED",
            damage_penalty=100.0,
            withdraw_from_stock=True,
            admin_notes="Cilt ağır hasarlı, onarıma ayrıldı ve 100 TL hasar tazminatı yansıtıldı",
        ),
    )
    assert final_ret.status == BorrowingStatus.RETURNED
    assert final_ret.approval_status == "APPROVED"
    assert final_ret.return_condition == "DAMAGED"
    assert final_ret.damage_penalty == 100.0
    assert final_ret.penalty_amount == 100.0
    assert final_ret.is_penalty_paid is False
    db_session.refresh(test_book)
    assert test_book.stock_count == 2  # Hasarlı kopya rafa geri dönmedi

    # 5. Admin manuel olarak 1 adet kayıp raporu ve 2 adet yeni stok girişi ekler
    service.create_manual_stock_movement(
        db_session,
        admin_user,
        StockMovementCreate(
            book_id=test_book.id,
            movement_type="ADMIN_LOST",
            quantity=1,
            notes="Yıllık envanter sayımında 1 adet kayıp tespit edildi",
        ),
    )
    db_session.refresh(test_book)
    assert test_book.stock_count == 1

    service.create_manual_stock_movement(
        db_session,
        admin_user,
        StockMovementCreate(
            book_id=test_book.id,
            movement_type="ADMIN_RESTOCK",
            quantity=2,
            notes="Yayınevinden 2 yeni kopya tedarik edildi",
        ),
    )
    db_session.refresh(test_book)
    assert test_book.stock_count == 3

    # 6. Kitap bazlı okuma ve stok geçmişi raporunu doğrula
    history = service.get_book_history(db_session, test_book.id)
    assert history.book_id == test_book.id
    assert history.current_stock == 3
    assert history.stats.total_borrow_count == 1
    assert history.stats.returned_count == 1
    assert history.stats.damaged_count == 1
    assert history.stats.lost_count == 1
    assert history.stats.total_damage_loss_penalty == 100.0
    assert len(history.reading_history) == 1
    assert len(history.stock_movements) >= 4


def test_ban_user_and_lost_damaged_blocking_and_alerts(
    db_session, test_user, test_book
):
    from app.modules.admin import service as admin_service
    from app.modules.auth import service as auth_service
    from app.modules.borrowing.schemas import AdminApproveReturnRequest, BorrowingReturn
    from app.modules.catalog.models import Book
    from app.modules.review import service as review_service
    from app.modules.review.schemas import ReviewCreate

    admin_user = User(
        email="admin_ban_test@kutuphane.com",
        password_hash="hashed",
        first_name="Ban",
        last_name="Admin",
    )
    db_session.add(admin_user)
    second_book = Book(
        title="İkinci Test Kitabı",
        isbn="9789750000099",
        published_year=2024,
        stock_count=2,
    )
    db_session.add(second_book)
    db_session.commit()

    # 1. Kullanıcı kitabı ödünç alır ve KAYIP (LOST) olarak iade talebine gönderir
    borrow = service.create_borrowing(
        db_session,
        test_user,
        BorrowingCreate(
            book_id=test_book.id,
            due_date=date.today() + timedelta(days=10),
        ),
    )
    ret_lost_pending = service.return_borrowing(
        db_session,
        test_user,
        borrow.id,
        BorrowingReturn(
            request_approval=True,
            return_condition="LOST",
            return_notes="Kitabı kaybettim",
        ),
    )
    assert ret_lost_pending.approval_status == "PENDING_RETURN"
    assert ret_lost_pending.return_condition == "LOST"
    assert ret_lost_pending.damage_penalty == 250.0
    assert ret_lost_pending.penalty_amount == 250.0

    # 2. Kullanıcı kayıp/hasar ücretini ödemeden yeni kitap ödünç alamaz!
    with pytest.raises(service.BusinessRuleError) as exc_info:
        service.create_borrowing(
            db_session,
            test_user,
            BorrowingCreate(
                book_id=second_book.id,
                due_date=date.today() + timedelta(days=7),
            ),
        )
    assert "hasar/kayıp" in str(exc_info.value) or "gecikme cezanız" in str(exc_info.value)

    # 3. Admin kayıp iadesini onayladığında stok hareketlerinde quantity_change == -1 görünür
    service.admin_approve_return(
        db_session,
        admin_user,
        borrow.id,
        AdminApproveReturnRequest(
            return_condition="LOST",
            damage_penalty=250.0,
            withdraw_from_stock=True,
        ),
    )
    summary = service.get_stock_movements_summary(db_session, book_id=test_book.id)
    assert summary.lost_count == 1
    assert summary.total_damage_lost_penalty == 250.0
    return_lost_mov = next(m for m in summary.items if m.movement_type == "RETURN_LOST")
    assert return_lost_mov.quantity_change == -1
    assert return_lost_mov.stock_before == return_lost_mov.stock_after + 1

    # 4. Ceza ödendiğinde borç bloku kalkar; ancak Admin kullanıcıyı banlarsa (not düşerek)
    # ödünç alma, rezervasyon ve yorum yapma engellenir!
    service.pay_borrowing_penalty(db_session, test_user, borrow.id)

    ban_note = "Kitap iadeniz yapılana kadar hesabınız yeni kitap ödünç almaya, rezervasyon yapmaya ve yorum yapmaya kapalı olacaktır."
    banned_info = admin_service.ban_user(db_session, admin_user, test_user.id, ban_note)
    assert banned_info.is_banned is True
    assert banned_info.ban_reason == ban_note

    # Giriş sonrası /auth/me uyarı bilgisinde ban durumu görünür
    me_alert = auth_service.build_user_read_with_alerts(db_session, test_user)
    assert me_alert.is_banned is True
    assert me_alert.ban_reason == ban_note

    with pytest.raises(service.BusinessRuleError) as ban_exc:
        service.create_borrowing(
            db_session,
            test_user,
            BorrowingCreate(
                book_id=second_book.id,
                due_date=date.today() + timedelta(days=7),
            ),
        )
    assert ban_note in str(ban_exc.value)

    with pytest.raises(review_service.BusinessRuleError) as rev_exc:
        review_service.create_review(
            db_session,
            test_user,
            ReviewCreate(book_id=test_book.id, rating=5, comment="Harika bir eser"),
        )
    assert ban_note in str(rev_exc.value)

    # 5. Admin banı kaldırdığında kullanıcı tekrar ödünç alabilir ve yorum yapabilir
    unbanned_info = admin_service.unban_user(db_session, admin_user, test_user.id)
    assert unbanned_info.is_banned is False

    new_borrow = service.create_borrowing(
        db_session,
        test_user,
        BorrowingCreate(
            book_id=second_book.id,
            due_date=date.today() + timedelta(days=7),
        ),
    )
    assert new_borrow.id is not None





