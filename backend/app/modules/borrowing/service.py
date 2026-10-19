import logging
import uuid
from datetime import date
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.auth.models import User
from app.modules.borrowing.models import Borrowing, BorrowingStatus, Reservation, ReservationStatus
from app.modules.borrowing.schemas import BorrowingCreate, ReservationCreate
from app.modules.catalog.models import Book

logger = logging.getLogger(__name__)


class BusinessRuleError(Exception):
    pass


class NotFoundError(Exception):
    pass


def create_borrowing(db: Session, user: User, data: BorrowingCreate) -> Borrowing:
    """Kitap ödünç alır, stok azaltır. Atomic işlem ve constraintlerle korunur."""
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

    # Race condition koruması için atomic update
    book.stock_count = Book.stock_count - 1

    borrowing = Borrowing(
        user_id=user.id,
        book_id=book.id,
        due_date=data.due_date,
    )
    db.add(borrowing)

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
    """Kitabı iade eder, stok artırır."""
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

    borrowing.status = BorrowingStatus.RETURNED
    borrowing.return_date = date.today()

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
    """Kullanıcı için rezervasyon oluşturur."""
    book = db.get(Book, data.book_id)
    if not book:
        logger.warning(
            "Rezervasyon başarısız: Kitap bulunamadı -> book_id: %s, user_id: %s",
            data.book_id,
            user.id,
        )
        raise NotFoundError("Kitap bulunamadı")

    reservation = Reservation(
        user_id=user.id,
        book_id=book.id,
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

    db.refresh(reservation)
    logger.info(
        "Rezervasyon başarıyla oluşturuldu -> reservation_id: %s, book_id: %s, user_id: %s",
        reservation.id,
        book.id,
        user.id,
    )
    return reservation


def get_user_reservations(db: Session, user: User) -> Sequence[Reservation]:
    """Kullanıcının rezervasyonlarını tarihe göre sıralı döner."""
    stmt = (
        select(Reservation)
        .where(Reservation.user_id == user.id)
        .order_by(Reservation.reservation_date.desc())
    )
    return db.scalars(stmt).all()
