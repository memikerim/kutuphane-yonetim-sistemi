import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.auth.models import User
from app.modules.borrowing.models import (
    Borrowing,
    BorrowingStatus,
    Reservation,
    ReservationStatus,
    _ensure_utc,
)
from app.modules.borrowing.schemas import BorrowingCreate, ReservationCreate
from app.modules.catalog.models import Book

logger = logging.getLogger(__name__)

MAX_ACTIVE_BORROWINGS = 3
RESERVATION_HOLD_HOURS = 24
OVERDUE_OR_PENALTY_BLOCK_MSG = (
    "Ödenmemiş gecikme cezanız veya süresi geçmiş kitabınız bulunduğu için yeni işlem yapamazsınız."
)


class BusinessRuleError(Exception):
    pass


class NotFoundError(Exception):
    pass


def sync_overdue_borrowings(db: Session, user_id: uuid.UUID | None = None) -> None:
    """Teslim tarihi (due_date) geçmiş ACTIVE ödünç kayıtlarının durumunu OVERDUE olarak günceller."""
    today = date.today()
    stmt = select(Borrowing).where(
        Borrowing.status == BorrowingStatus.ACTIVE,
        Borrowing.due_date < today,
    )
    if user_id is not None:
        stmt = stmt.where(Borrowing.user_id == user_id)

    overdue_items = list(db.scalars(stmt).all())
    if overdue_items:
        for b in overdue_items:
            b.status = BorrowingStatus.OVERDUE
        db.commit()


def _check_user_overdue_or_unpaid_penalty(db: Session, user: User) -> None:
    """
    Kullanıcının süresi geçmiş aktif bir ödünç kitabı (OVERDUE) veya
    ödenmemiş gecikme cezası (penalty_amount > 0 ve is_penalty_paid == False) varsa 400 fırlatır.
    """
    sync_overdue_borrowings(db, user.id)
    today = date.today()

    user_borrowings = list(
        db.scalars(select(Borrowing).where(Borrowing.user_id == user.id)).all()
    )
    for b in user_borrowings:
        is_overdue_active = b.status != BorrowingStatus.RETURNED and (
            b.status == BorrowingStatus.OVERDUE or b.due_date < today
        )
        has_unpaid_penalty = (b.penalty_amount or 0.0) > 0 and not b.is_penalty_paid

        if is_overdue_active or has_unpaid_penalty:
            logger.warning(
                "İşlem engellendi (Gecikmiş kitap veya ödenmemiş ceza mevcut) -> user_id: %s, borrow_id: %s, status: %s, penalty: %.2f, paid: %s",
                user.id,
                b.id,
                b.status,
                b.penalty_amount or 0.0,
                b.is_penalty_paid,
            )
            raise BusinessRuleError(OVERDUE_OR_PENALTY_BLOCK_MSG)



def sync_reservations(db: Session, book_id: uuid.UUID | None = None) -> None:
    """
    Rezervasyon kuyruğunu senkronize eder:
    1. Kullanıcının zaten aktif olarak ödünç aldığı (ACTIVE/OVERDUE) kitaplara ait
       bekleyen (PENDING) rezervasyonları listeden siler.
    2. 24 saatlik ödünç alma süresi (expires_at) dolmuş olan PENDING rezervasyonları
       listeden siler ve sıradaki bir sonraki kullanıcıya hakkı devreder.
    3. Kitap stoğu mevcutsa (stock_count > 0), kuyruğun başındaki ilk `stock_count`
       kadar rezervasyon için 24 saatlik süreyi (expires_at) başlatır; kuyrukta daha
       geride bekleyenlerin süresini ise sıra kendilerine gelene kadar None tutar.
    """
    now = datetime.now(timezone.utc)

    stmt = select(Reservation).where(Reservation.status == ReservationStatus.PENDING)
    if book_id is not None:
        stmt = stmt.where(Reservation.book_id == book_id)

    pending_list = list(db.scalars(stmt).all())
    if not pending_list:
        return

    by_book: dict[uuid.UUID, list[Reservation]] = {}
    for res in pending_list:
        by_book.setdefault(res.book_id, []).append(res)

    changed_books: list[Book] = []

    for b_id, book_reservations in by_book.items():
        book = db.get(Book, b_id)
        if not book:
            continue

        book_changed = False
        book_reservations.sort(
            key=lambda r: (
                _ensure_utc(r.reservation_date).timestamp() if r.reservation_date else 0.0,
                str(r.id),
            )
        )

        # 1. Kullanıcının bu kitabı zaten ACTIVE/OVERDUE olarak ödünç alıp almadığını kontrol et
        active_borrower_ids = set(
            db.scalars(
                select(Borrowing.user_id).where(
                    Borrowing.book_id == b_id,
                    Borrowing.status.in_([BorrowingStatus.ACTIVE, BorrowingStatus.OVERDUE]),
                )
            ).all()
        )

        queue: list[Reservation] = []
        for res in book_reservations:
            if res.user_id in active_borrower_ids:
                db.delete(res)
                book_changed = True
            else:
                queue.append(res)

        stock = max(0, book.stock_count or 0)

        if stock == 0:
            for res in list(queue):
                if res.expires_at is not None and _ensure_utc(res.expires_at) <= now:
                    db.delete(res)
                    queue.remove(res)
                    book_changed = True
                elif res.expires_at is not None:
                    res.expires_at = None
                    book_changed = True
        else:
            while True:
                expired_found = False
                for res in list(queue[:stock]):
                    if res.expires_at is not None and _ensure_utc(res.expires_at) <= now:
                        logger.info(
                            "Rezervasyon 24 saat içinde ödünç alınmadığı için silindi -> reservation_id: %s, user_id: %s, book_id: %s",
                            res.id,
                            res.user_id,
                            b_id,
                        )
                        db.delete(res)
                        queue.remove(res)
                        book_changed = True
                        expired_found = True
                if not expired_found:
                    break

            for idx, res in enumerate(queue):
                if idx < stock:
                    if res.expires_at is None:
                        res.expires_at = now + timedelta(hours=RESERVATION_HOLD_HOURS)
                        book_changed = True
                else:
                    if res.expires_at is not None:
                        res.expires_at = None
                        book_changed = True

        if book_changed:
            changed_books.append(book)

    if changed_books:
        db.commit()
        for b in changed_books:
            db.expire(b, ["reservations"])


def create_borrowing(db: Session, user: User, data: BorrowingCreate) -> Borrowing:
    """Kitap ödünç alır, stok azaltır. Rezervasyon sırası, kota ve constraintlerle korunur."""
    book = db.get(Book, data.book_id)
    if not book:
        logger.warning(
            "Ödünç alma başarısız: Kitap bulunamadı -> book_id: %s, user_id: %s",
            data.book_id,
            user.id,
        )
        raise NotFoundError("Kitap bulunamadı")

    if data.due_date < date.today():
        logger.warning(
            "Ödünç alma başarısız: Geçmiş tarihli iade tarihi -> due_date: %s, user_id: %s",
            data.due_date,
            user.id,
        )
        raise BusinessRuleError("İade tarihi (due_date) geçmiş bir tarih olamaz")

    # Önce bu kitaba ait rezervasyon kuyruğunu ve süre aşımını senkronize et
    sync_reservations(db, book.id)
    db.refresh(book)

    # Kural 0: Gecikmiş (OVERDUE) kitabı veya ödenmemiş cezası olan kullanıcı yeni kitap ödünç alamaz
    _check_user_overdue_or_unpaid_penalty(db, user)

    # Kural 1: Kullanıcı aynı kitabı iade etmeden (ACTIVE/OVERDUE iken) ikinci kez ödünç alamaz
    existing_active_for_book = db.scalar(
        select(Borrowing).where(
            Borrowing.user_id == user.id,
            Borrowing.book_id == book.id,
            Borrowing.status.in_([BorrowingStatus.ACTIVE, BorrowingStatus.OVERDUE]),
        )
    )
    if existing_active_for_book is not None:
        logger.warning(
            "Ödünç alma başarısız: Kullanıcının elinde aynı kitaptan aktif ödünç var -> book_id: %s, user_id: %s",
            book.id,
            user.id,
        )
        raise BusinessRuleError(
            "Bu kitap zaten şu an üzerinizde ödünç alınmış durumda. İade etmeden tekrar ödünç alamazsınız."
        )

    # Kural 2: Bir kullanıcı aynı anda en fazla MAX_ACTIVE_BORROWINGS (3) adet aktif kitap tutabilir
    active_count = db.scalar(
        select(func.count())
        .select_from(Borrowing)
        .where(
            Borrowing.user_id == user.id,
            Borrowing.status.in_([BorrowingStatus.ACTIVE, BorrowingStatus.OVERDUE]),
        )
    )
    if (active_count or 0) >= MAX_ACTIVE_BORROWINGS:
        logger.warning(
            "Ödünç alma başarısız: Maksimum aktif kitap kotası (%d) doldu -> user_id: %s",
            MAX_ACTIVE_BORROWINGS,
            user.id,
        )
        raise BusinessRuleError(
            f"Aynı anda en fazla {MAX_ACTIVE_BORROWINGS} adet kitap ödünç alabilirsiniz. Yeni kitap almak için mevcut kitaplarınızdan birini iade edin."
        )

    # Kural 3: Rezervasyon Kuyruğu ve Stok Kilidi Kontrolü
    pending_reservations = list(
        db.scalars(
            select(Reservation).where(
                Reservation.book_id == book.id,
                Reservation.status == ReservationStatus.PENDING,
            )
        ).all()
    )
    pending_reservations.sort(
        key=lambda r: (
            r.reservation_date.timestamp() if r.reservation_date else 0.0,
            str(r.id),
        )
    )

    user_res: Reservation | None = None
    user_queue_pos: int | None = None
    for idx, r in enumerate(pending_reservations):
        if r.user_id == user.id:
            user_res = r
            user_queue_pos = idx + 1
            break

    if book.stock_count > 0:
        has_reserved_slot = user_res is not None and user_queue_pos is not None and user_queue_pos <= book.stock_count
        if not has_reserved_slot:
            unreserved_stock = book.stock_count - len(pending_reservations)
            if unreserved_stock <= 0:
                if user_queue_pos is not None:
                    raise BusinessRuleError(
                        f"Bu kitabın mevcut stoğu sıradaki ilk kullanıcı(lar) için ayrılmıştır. "
                        f"Rezerve listesinde {user_queue_pos}. sıradasınız; diğer kullanıcılar süreleri bitene kadar ödünç almazlarsa ödünç alabilirsiniz."
                    )
                raise BusinessRuleError(
                    "Bu kitabın mevcut stoğu başka bir kullanıcı tarafından rezerve edilmiştir (24 saat geçerli). "
                    "Şu an ödünç alamazsınız, sadece rezerve ederek sıraya girebilirsiniz."
                )

    # Race condition koruması için atomic update
    book.stock_count = Book.stock_count - 1

    borrowing = Borrowing(
        user_id=user.id,
        book_id=book.id,
        due_date=data.due_date,
    )
    db.add(borrowing)

    # Eğer kullanıcının bu kitap için rezervasyonu varsa ödünç alındığı anda rezerve listesinden silinir
    if user_res is not None:
        db.delete(user_res)

    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        error_msg = str(e.orig) if e.orig else ""
        if "ck_books_stock_count_non_negative" in error_msg or "stock_count >= 0" in error_msg or "CHECK constraint failed" in error_msg:
            logger.warning(
                "Ödünç alma başarısız: Stok yetersiz (Stok=0) -> book_id: %s, user_id: %s",
                book.id,
                user.id,
            )
            raise BusinessRuleError("Bu kitap şu an stokta yok (Stok=0)")
        logger.error(
            "Ödünç alma sırasında beklenmeyen veritabanı kısıtlama hatası -> user_id: %s, error: %s",
            user.id,
            e,
            exc_info=True,
        )
        raise BusinessRuleError("Ödünç alma işlemi gerçekleştirilemedi")

    db.expire(book, ["reservations"])
    sync_reservations(db, book.id)
    db.refresh(borrowing)
    logger.info(
        "Kitap başarıyla ödünç alındı -> borrow_id: %s, book_id: %s, user_id: %s, due_date: %s",
        borrowing.id,
        book.id,
        user.id,
        borrowing.due_date,
    )
    return borrowing


def return_borrowing(db: Session, user: User, borrowing_id: uuid.UUID) -> Borrowing:
    """Kitabı iade eder, stok artırır ve varsa sırada bekleyen rezervasyonun 24 saatlik süresini başlatır."""
    borrowing = db.get(Borrowing, borrowing_id)
    if not borrowing:
        logger.warning(
            "İade başarısız: Ödünç alma kaydı bulunamadı -> borrow_id: %s, user_id: %s",
            borrowing_id,
            user.id,
        )
        raise NotFoundError("Ödünç alma kaydı bulunamadı")

    if borrowing.user_id != user.id:
        logger.warning(
            "İade başarısız: Kayıt kullanıcıya ait değil -> borrow_id: %s, requester: %s, owner: %s",
            borrowing_id,
            user.id,
            borrowing.user_id,
        )
        raise BusinessRuleError("Bu ödünç alma kaydı size ait değil")

    if borrowing.status == BorrowingStatus.RETURNED:
        logger.warning(
            "İade başarısız: Kitap zaten iade edilmiş -> borrow_id: %s, user_id: %s",
            borrowing_id,
            user.id,
        )
        raise BusinessRuleError("Bu kitap zaten iade edilmiş")

    today = date.today()
    borrowing.status = BorrowingStatus.RETURNED
    borrowing.return_date = today

    if today > borrowing.due_date:
        overdue_days = (today - borrowing.due_date).days
        penalty = round(overdue_days * settings.DAILY_PENALTY_RATE, 2)
        borrowing.penalty_amount = penalty
        borrowing.is_penalty_paid = False
        logger.warning(
            "Gecikmeli iade: Ceza oluşturuldu -> borrow_id: %s, user_id: %s, overdue_days: %d, penalty_amount: %.2f TL",
            borrowing.id,
            user.id,
            overdue_days,
            penalty,
        )
    else:
        borrowing.penalty_amount = 0.0
        borrowing.is_penalty_paid = False

    # Stok iadesi (atomic update)
    book = db.get(Book, borrowing.book_id)
    if book:
        book.stock_count = Book.stock_count + 1

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        logger.error(
            "İade işlemi sırasında veritabanı hatası -> borrow_id: %s, error: %s",
            borrowing_id,
            exc,
            exc_info=True,
        )
        raise BusinessRuleError("İade işlemi sırasında veritabanı hatası oluştu")

    # Kitap stoğu arttığı anda sırada bekleyen rezervasyon varsa 24 saatlik süresini başlat
    if book:
        db.refresh(book)
        sync_reservations(db, book.id)

    db.refresh(borrowing)
    logger.info(
        "Kitap başarıyla iade edildi -> borrow_id: %s, book_id: %s, user_id: %s, return_date: %s",
        borrowing.id,
        borrowing.book_id,
        user.id,
        borrowing.return_date,
    )
    return borrowing


def create_reservation(db: Session, user: User, data: ReservationCreate) -> Reservation:
    """Kullanıcı için rezervasyon oluşturur ve stok uygunluğuna göre 24 saatlik süreyi veya sıra bilgisini ayarlar."""
    book = db.get(Book, data.book_id)
    if not book:
        logger.warning(
            "Rezervasyon başarısız: Kitap bulunamadı -> book_id: %s, user_id: %s",
            data.book_id,
            user.id,
        )
        raise NotFoundError("Kitap bulunamadı")

    sync_reservations(db, book.id)

    # Gecikmiş (OVERDUE) kitabı veya ödenmemiş cezası olan kullanıcı rezervasyon yapamaz
    _check_user_overdue_or_unpaid_penalty(db, user)

    # Kullanıcının zaten elinde aktif olarak bu kitap varsa rezerve edemez
    existing_active_borrowing = db.scalar(
        select(Borrowing).where(
            Borrowing.user_id == user.id,
            Borrowing.book_id == book.id,
            Borrowing.status.in_([BorrowingStatus.ACTIVE, BorrowingStatus.OVERDUE]),
        )
    )
    if existing_active_borrowing is not None:
        raise BusinessRuleError(
            "Bu kitap zaten şu an üzerinizde ödünç alınmış durumda. Elinizdeki kitabı rezerve edemezsiniz."
        )

    now = datetime.now(timezone.utc)
    latest_date = db.scalar(
        select(func.max(Reservation.reservation_date)).where(
            Reservation.book_id == book.id,
            Reservation.status == ReservationStatus.PENDING,
        )
    )
    if latest_date is not None:
        latest_utc = _ensure_utc(latest_date)
        if now <= latest_utc:
            now = latest_utc + timedelta(microseconds=10)

    reservation = Reservation(
        user_id=user.id,
        book_id=book.id,
        reservation_date=now,
    )
    db.add(reservation)

    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        error_msg = str(e.orig) if e.orig else ""
        if "uq_reservations_user_book_pending" in error_msg or "reservations.user_id" in error_msg:
            logger.warning(
                "Rezervasyon reddedildi: Kullanıcının zaten bekleyen rezervasyonu var -> book_id: %s, user_id: %s",
                data.book_id,
                user.id,
            )
            raise BusinessRuleError("Bu kitap için zaten bekleyen (PENDING) bir rezervasyonunuz var")
        logger.error(
            "Rezervasyon sırasında beklenmeyen veritabanı hatası -> user_id: %s, error: %s",
            user.id,
            e,
            exc_info=True,
        )
        raise BusinessRuleError("Rezervasyon işlemi gerçekleştirilemedi")

    db.expire(book, ["reservations"])
    sync_reservations(db, book.id)
    db.refresh(reservation)
    logger.info(
        "Rezervasyon başarıyla oluşturuldu -> reservation_id: %s, book_id: %s, user_id: %s, queue_pos: %s",
        reservation.id,
        book.id,
        user.id,
        reservation.queue_position,
    )
    return reservation


def cancel_reservation(db: Session, user: User, reservation_id: uuid.UUID) -> None:
    """Kullanıcının bekleyen rezervasyonunu iptal edip rezerve listesinden siler."""
    reservation = db.get(Reservation, reservation_id)
    if not reservation:
        raise NotFoundError("Rezervasyon kaydı bulunamadı")
    if reservation.user_id != user.id:
        raise BusinessRuleError("Bu rezervasyon kaydı size ait değil")

    book_id = reservation.book_id
    book = db.get(Book, book_id)
    db.delete(reservation)
    db.commit()

    if book:
        db.expire(book, ["reservations"])
    sync_reservations(db, book_id)


def pay_borrowing_penalty(db: Session, user: User, borrowing_id: uuid.UUID) -> Borrowing:
    """Kullanıcının ilgili ödünç işlemine ait gecikme cezasını ödediğini işaretler (is_penalty_paid = True)."""
    borrowing = db.get(Borrowing, borrowing_id)
    if not borrowing:
        logger.warning(
            "Ceza ödeme başarısız: Ödünç kaydı bulunamadı -> borrow_id: %s, user_id: %s",
            borrowing_id,
            user.id,
        )
        raise NotFoundError("Ödünç alma kaydı bulunamadı")

    if borrowing.user_id != user.id:
        logger.warning(
            "Ceza ödeme başarısız: Kayıt kullanıcıya ait değil -> borrow_id: %s, requester: %s, owner: %s",
            borrowing_id,
            user.id,
            borrowing.user_id,
        )
        raise BusinessRuleError("Bu ödünç alma kaydı size ait değil")

    if (borrowing.penalty_amount or 0.0) <= 0.0:
        raise BusinessRuleError("Bu kayıt için ödenecek bir gecikme cezası bulunmamaktadır")

    if borrowing.is_penalty_paid:
        raise BusinessRuleError("Bu gecikme cezası zaten ödenmiş")

    borrowing.is_penalty_paid = True
    db.commit()
    db.refresh(borrowing)
    logger.info(
        "Gecikme cezası başarıyla ödendi -> borrow_id: %s, user_id: %s, penalty_amount: %.2f TL",
        borrowing.id,
        user.id,
        borrowing.penalty_amount,
    )
    return borrowing


def simulate_overdue_borrowing(db: Session, borrowing_id: uuid.UUID) -> Borrowing:
    """
    Canlı sunum / test için seçilen aktif ödünç kaydının due_date değerini 5 gün öncesine çeker
    ve durumunu OVERDUE yapar.
    """
    borrowing = db.get(Borrowing, borrowing_id)
    if not borrowing:
        raise NotFoundError("Ödünç alma kaydı bulunamadı")

    if borrowing.status == BorrowingStatus.RETURNED:
        raise BusinessRuleError("İade edilmiş bir kayda gecikme simülasyonu uygulanamaz")

    today = date.today()
    # Eğer due_date bugün veya gelecekteyse doğrudan bugünden 5 gün öncesine çek; zaten geçmişteyse 5 gün daha geri çek
    if borrowing.due_date >= today:
        new_due_date = today - timedelta(days=5)
    else:
        new_due_date = borrowing.due_date - timedelta(days=5)

    # CheckConstraint (due_date >= borrow_date) ihlalini önlemek için borrow_date'i de uyumlu çek
    if borrowing.borrow_date > new_due_date:
        borrowing.borrow_date = new_due_date - timedelta(days=14)

    borrowing.due_date = new_due_date
    borrowing.status = BorrowingStatus.OVERDUE

    db.commit()
    db.refresh(borrowing)
    logger.info(
        "Gecikme simülasyonu uygulandı (-5 gün) -> borrow_id: %s, user_id: %s, new_due_date: %s, status: %s",
        borrowing.id,
        borrowing.user_id,
        borrowing.due_date,
        borrowing.status,
    )
    return borrowing


def get_all_borrowings(db: Session) -> Sequence[Borrowing]:
    """Tüm ödünç işlemlerini (ADMIN paneli için) tarihe göre sıralı döner."""
    sync_overdue_borrowings(db)
    sync_reservations(db)
    stmt = select(Borrowing).order_by(Borrowing.borrow_date.desc())
    return db.scalars(stmt).all()


def get_user_borrowings(db: Session, user: User) -> Sequence[Borrowing]:
    """Kullanıcının ödünç aldığı kitapları (aktif ve geçmiş) tarihe göre sıralı döner."""
    sync_overdue_borrowings(db, user.id)
    sync_reservations(db)
    stmt = (
        select(Borrowing)
        .where(Borrowing.user_id == user.id)
        .order_by(Borrowing.borrow_date.desc())
    )
    return db.scalars(stmt).all()



def get_user_reservations(db: Session, user: User) -> Sequence[Reservation]:
    """Kullanıcının aktif (PENDING) rezervasyonlarını tarihe göre sıralı döner (süresi bitenler ve ödünç alınanlar otomatik silinir)."""
    sync_reservations(db)
    stmt = (
        select(Reservation)
        .where(
            Reservation.user_id == user.id,
            Reservation.status == ReservationStatus.PENDING,
        )
        .order_by(Reservation.reservation_date.asc())
    )
    return db.scalars(stmt).all()


