import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.auth.models import RoleName, User
from app.modules.borrowing.models import (
    Borrowing,
    BorrowingStatus,
    Reservation,
    ReservationStatus,
    StockMovement,
    _ensure_utc,
)
from app.modules.borrowing.schemas import (
    AdminApproveReturnRequest,
    BookHistoryResponse,
    BookHistoryStats,
    BookReadingRecord,
    BorrowingCreate,
    BorrowingReturn,
    ReservationCreate,
    StockMovementCreate,
    StockMovementRead,
    StockMovementSummaryResponse,
)
from app.modules.catalog.models import Book

logger = logging.getLogger(__name__)

MAX_ACTIVE_BORROWINGS = 3
RESERVATION_HOLD_HOURS = 24
OVERDUE_OR_PENALTY_BLOCK_MSG = (
    "Ödenmemiş gecikme cezanız veya süresi geçmiş kitabınız ya da ödenmemiş hasar/kayıp tazminat borcunuz bulunduğu için yeni işlem yapamazsınız."
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
        Borrowing.approval_status != "PENDING_BORROW",
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
    Kullanıcı banlıysa (is_banned == True), süresi geçmiş aktif bir ödünç kitabı (OVERDUE) varsa,
    hasarlı/kayıp olarak işaretlenmiş kitabı varsa veya ödenmemiş gecikme / hasar / kayıp
    tazminat borcu (penalty_amount > 0 ve is_penalty_paid == False) varsa 400 fırlatır.
    """
    if getattr(user, "is_banned", False):
        reason = getattr(user, "ban_reason", None) or (
            "Kitap iadeniz ve borç ödemeniz tamamlanana kadar hesabınız yeni kitap ödünç almaya, "
            "rezervasyon yapmaya ve yorum yapmaya kapalı olacaktır."
        )
        logger.warning(
            "İşlem engellendi (Kullanıcı banlı) -> user_id: %s, reason: %s",
            user.id,
            reason,
        )
        raise BusinessRuleError(f"Hesabınız yönetici tarafından kısıtlanmıştır: {reason}")

    sync_overdue_borrowings(db, user.id)
    today = date.today()

    user_borrowings = list(
        db.scalars(select(Borrowing).where(Borrowing.user_id == user.id)).all()
    )
    for b in user_borrowings:
        cond = (b.return_condition or "GOOD").upper()
        payment_status = getattr(b, "penalty_payment_status", "UNPAID")
        is_overdue_active = (
            b.status != BorrowingStatus.RETURNED
            and b.approval_status != "PENDING_BORROW"
            and (b.status == BorrowingStatus.OVERDUE or b.due_date < today)
        )
        is_damaged_or_lost_pending = (
            b.status != BorrowingStatus.RETURNED and cond in ("DAMAGED", "LOST")
        )
        has_unpaid_penalty = (
            ((b.penalty_amount or 0.0) > 0 or (b.damage_penalty or 0.0) > 0)
            and not b.is_penalty_paid
        )

        # Kullanıcı ödeme yapmış ama yönetici henüz onaylamamışsa (PENDING_APPROVAL)
        if payment_status == "PENDING_APPROVAL":
            logger.warning(
                "İşlem engellendi (Ödeme yönetici onayı bekliyor) -> user_id: %s, borrow_id: %s, penalty: %.2f",
                user.id,
                b.id,
                b.penalty_amount or 0.0,
            )
            raise BusinessRuleError(
                "Ödemiş olduğunuz gecikme veya kayıp/hasar tazminat bedelinin yönetici tarafından onaylanması beklenmektedir. "
                "Yönetici ödemeyi aldığını onaylayana kadar yeni kitap ödünç alamaz veya rezervasyon oluşturamazsınız."
            )

        if is_overdue_active or is_damaged_or_lost_pending or has_unpaid_penalty:
            logger.warning(
                "İşlem engellendi (Gecikmiş kitap, hasar/kayıp bildirimi veya ödenmemiş borç mevcut) -> user_id: %s, borrow_id: %s, status: %s, cond: %s, penalty: %.2f, paid: %s",
                user.id,
                b.id,
                b.status,
                cond,
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
       ÖNEMLİ: Sıradaki kullanıcının 24 saatlik süresi, kullanıcının tekrar giriş yapmasını
       beklemeden, bir önceki kullanıcının süresinin bittiği an (slot_freed_at) itibarıyla
       otomatik olarak başlar ve zincirleme (cascade) olarak hesaplanır.
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
                if res.expires_at is not None:
                    res.expires_at = None
                    book_changed = True
        else:
            # 2. Aktif slotta (ilk `stock` sırada) süresi dolmuş rezervasyonları kronolojik sırayla
            # düşür ve sıradaki kullanıcının 24 saatlik süresini bir önceki sürenin bittiği
            # `slot_freed_at` anından itibaren (giriş yapmasını beklemeden) başlat.
            while True:
                expired_candidates = [
                    r
                    for r in queue[:stock]
                    if r.expires_at is not None and _ensure_utc(r.expires_at) <= now
                ]
                if not expired_candidates:
                    break

                expired_candidates.sort(key=lambda r: _ensure_utc(r.expires_at))
                expired_res = expired_candidates[0]
                slot_freed_at = _ensure_utc(expired_res.expires_at)

                logger.info(
                    "Rezervasyon 24 saat içinde ödünç alınmadığı için silindi -> reservation_id: %s, user_id: %s, book_id: %s, expired_at: %s",
                    expired_res.id,
                    expired_res.user_id,
                    b_id,
                    slot_freed_at.isoformat(),
                )
                db.delete(expired_res)
                queue.remove(expired_res)
                book_changed = True

                # Sırası gelen bir sonraki rezervasyonun sayacını `now` yerine `slot_freed_at` anından başlat
                for candidate in queue[:stock]:
                    if candidate.expires_at is None:
                        candidate.expires_at = slot_freed_at + timedelta(
                            hours=RESERVATION_HOLD_HOURS
                        )
                        logger.info(
                            "Rezervasyon sırası sıradaki kullanıcıya devredildi ve 24 saatlik sayaç otomatik başladı -> reservation_id: %s, user_id: %s, book_id: %s, start_at: %s, expires_at: %s",
                            candidate.id,
                            candidate.user_id,
                            b_id,
                            slot_freed_at.isoformat(),
                            candidate.expires_at.isoformat(),
                        )
                        break

            # 3. Stok yeni açıldıysa veya yeni rezervasyon yapıldıysa aktif slottaki
            # rezervasyonların 24 saatlik süresini hemen başlat
            for idx, res in enumerate(queue):
                if idx < stock:
                    if res.expires_at is None:
                        res.expires_at = now + timedelta(hours=RESERVATION_HOLD_HOURS)
                        book_changed = True
                        logger.info(
                            "Kitap stoğuna istinaden rezervasyon için 24 saatlik ödünç alma süresi başlatıldı -> reservation_id: %s, user_id: %s, book_id: %s, expires_at: %s",
                            res.id,
                            res.user_id,
                            b_id,
                            res.expires_at.isoformat(),
                        )
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

    stock_before = int(book.stock_count or 0)
    # Race condition koruması için atomic update
    book.stock_count = Book.stock_count - 1

    approval_status = "PENDING_BORROW" if getattr(data, "request_approval", False) else "APPROVED"
    borrowing = Borrowing(
        user_id=user.id,
        book_id=book.id,
        due_date=data.due_date,
        approval_status=approval_status,
        return_notes=getattr(data, "notes", None),
    )
    db.add(borrowing)

    # Eğer kullanıcının bu kitap için rezervasyonu varsa ödünç alındığı anda rezerve listesinden silinir
    if user_res is not None:
        db.delete(user_res)

    try:
        db.flush()
        movement = StockMovement(
            book_id=book.id,
            user_id=user.id,
            borrowing_id=borrowing.id,
            movement_type="BORROW_REQUEST" if approval_status == "PENDING_BORROW" else "BORROW_DIRECT",
            condition="GOOD",
            quantity_change=-1,
            stock_before=stock_before,
            stock_after=max(0, stock_before - 1),
            penalty_added=0.0,
            notes=(
                f"Ödünç talebi oluşturuldu (Görevli onayı bekleniyor). Not: {data.notes}"
                if approval_status == "PENDING_BORROW" and getattr(data, "notes", None)
                else "Ödünç talebi oluşturuldu (Görevli onayı bekleniyor)"
                if approval_status == "PENDING_BORROW"
                else "Kitap ödünç alındı"
            ),
        )
        db.add(movement)
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
        "Kitap ödünç işlemi kaydedildi -> borrow_id: %s, book_id: %s, user_id: %s, approval_status: %s, due_date: %s",
        borrowing.id,
        book.id,
        user.id,
        borrowing.approval_status,
        borrowing.due_date,
    )
    return borrowing


def _complete_return_transaction(
    db: Session,
    borrowing: Borrowing,
    cond: str = "GOOD",
    damage_penalty_override: float | None = None,
    withdraw_override: bool | None = None,
    admin_user: User | None = None,
    notes: str | None = None,
) -> Borrowing:
    cond = (cond or "GOOD").upper()
    if cond not in ("GOOD", "DAMAGED", "LOST"):
        cond = "GOOD"

    today = date.today()
    borrowing.status = BorrowingStatus.RETURNED
    borrowing.approval_status = "APPROVED"
    borrowing.return_date = today
    borrowing.return_condition = cond
    if notes and not admin_user:
        borrowing.return_notes = notes
    if admin_user and notes:
        borrowing.admin_notes = notes

    overdue_days = max(0, (today - borrowing.due_date).days) if today > borrowing.due_date else 0
    overdue_penalty = round(overdue_days * settings.DAILY_PENALTY_RATE, 2)

    if damage_penalty_override is not None:
        dmg_penalty = round(float(damage_penalty_override), 2)
    elif cond == "DAMAGED":
        dmg_penalty = float(settings.DAMAGED_BOOK_PENALTY)
    elif cond == "LOST":
        dmg_penalty = float(settings.LOST_BOOK_PENALTY)
    else:
        dmg_penalty = 0.0

    borrowing.damage_penalty = dmg_penalty
    total_penalty = round(overdue_penalty + dmg_penalty, 2)
    borrowing.penalty_amount = total_penalty
    borrowing.is_penalty_paid = False

    if total_penalty > 0:
        logger.warning(
            "İade sırasında ceza/tazminat oluştu -> borrow_id: %s, user_id: %s, condition: %s, overdue_days: %d, damage_penalty: %.2f, total: %.2f TL",
            borrowing.id,
            borrowing.user_id,
            cond,
            overdue_days,
            dmg_penalty,
            total_penalty,
        )

    book = db.get(Book, borrowing.book_id)
    current_shelf_stock = int(book.stock_count or 0) if book else 0

    if cond == "LOST":
        restore_to_stock = False
    elif cond == "DAMAGED":
        restore_to_stock = False if withdraw_override is None else (not withdraw_override)
    else:
        restore_to_stock = True

    if book and restore_to_stock:
        book.stock_count = Book.stock_count + 1
        qty_change = 1
        stock_before = current_shelf_stock
        stock_after = current_shelf_stock + 1
    else:
        # Kitap ödünç alındığında raftan -1 ayrılmıştı (ödünç öncesi toplam envanter = current_shelf_stock + 1).
        # Kitap KAYIP (LOST) veya AĞIR HASARLI (DAMAGED) olduğu için rafa geri eklenmez ve toplam stoktan -1 kalıcı olarak düşülür.
        qty_change = -1
        stock_before = current_shelf_stock + 1
        stock_after = current_shelf_stock

    movement_type = (
        "RETURN_GOOD"
        if cond == "GOOD"
        else "RETURN_DAMAGED"
        if cond == "DAMAGED"
        else "RETURN_LOST"
    )
    default_note = (
        "Kitap sağlam olarak iade alındı ve rafa eklendi (+1)"
        if cond == "GOOD"
        else f"Hasarlı kitap iadesi ({dmg_penalty:.0f} TL hasar tazminatı yansıtıldı)"
        if cond == "DAMAGED"
        else f"Kayıp kitap bildirimi ({dmg_penalty:.0f} TL kayıp bedeli yansıtıldı, 1 adet kalıcı stoktan düşüldü)"
    )
    combined_note = notes or borrowing.admin_notes or borrowing.return_notes or default_note

    if book:
        movement = StockMovement(
            book_id=book.id,
            user_id=borrowing.user_id,
            admin_id=admin_user.id if admin_user else None,
            borrowing_id=borrowing.id,
            movement_type=movement_type,
            condition=cond,
            quantity_change=qty_change,
            stock_before=stock_before,
            stock_after=stock_after,
            penalty_added=dmg_penalty,
            notes=combined_note,
        )
        db.add(movement)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        logger.error(
            "İade işlemi sırasında veritabanı hatası -> borrow_id: %s, error: %s",
            borrowing.id,
            exc,
            exc_info=True,
        )
        raise BusinessRuleError("İade işlemi sırasında veritabanı hatası oluştu")

    if book:
        db.refresh(book)
        sync_reservations(db, book.id)

    db.refresh(borrowing)
    logger.info(
        "Kitap başarıyla iade edildi -> borrow_id: %s, book_id: %s, user_id: %s, condition: %s, return_date: %s",
        borrowing.id,
        borrowing.book_id,
        borrowing.user_id,
        borrowing.return_condition,
        borrowing.return_date,
    )
    return borrowing


def return_borrowing(
    db: Session,
    user: User,
    borrowing_id: uuid.UUID,
    return_data: BorrowingReturn | None = None,
) -> Borrowing:
    """Kitabı iade eder veya görevli onay kuyruğuna (PENDING_RETURN) gönderir."""
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

    if borrowing.approval_status == "PENDING_BORROW":
        raise BusinessRuleError(
            "Henüz görevli tarafından onaylanmamış ödünç talebi iade edilemez; talebi iptal edebilirsiniz."
        )

    req_approval = bool(getattr(return_data, "request_approval", False)) if return_data else False
    cond = (getattr(return_data, "return_condition", "GOOD") or "GOOD").upper() if return_data else "GOOD"
    if cond not in ("GOOD", "DAMAGED", "LOST"):
        cond = "GOOD"
    notes = getattr(return_data, "return_notes", None) if return_data else None

    if req_approval:
        if borrowing.approval_status == "PENDING_RETURN":
            raise BusinessRuleError("Bu kitap için zaten görevli onayı bekleyen bir iade talebiniz bulunuyor")
        borrowing.approval_status = "PENDING_RETURN"
        borrowing.return_condition = cond
        if notes:
            borrowing.return_notes = notes

        # Kullanıcı kitabı HASARLI (DAMAGED) veya KAYIP (LOST) olarak işaretlediyse veya gecikme varsa
        # tahmini tazminat/gecikme borcunu hemen yansıt ki borç ödenene kadar yeni kitap ödünç alamasın.
        today = date.today()
        overdue_days = max(0, (today - borrowing.due_date).days) if today > borrowing.due_date else 0
        overdue_pen = round(overdue_days * settings.DAILY_PENALTY_RATE, 2)
        dmg_pen = (
            float(settings.DAMAGED_BOOK_PENALTY)
            if cond == "DAMAGED"
            else float(settings.LOST_BOOK_PENALTY)
            if cond == "LOST"
            else 0.0
        )
        if dmg_pen > 0 or overdue_pen > 0:
            borrowing.damage_penalty = dmg_pen
            borrowing.penalty_amount = round(overdue_pen + dmg_pen, 2)
            borrowing.is_penalty_paid = False

        db.commit()
        db.refresh(borrowing)
        logger.info(
            "İade ve fiziksel kontrol talebi oluşturuldu (Görevli onayı bekleniyor) -> borrow_id: %s, user_id: %s, condition: %s, penalty: %.2f",
            borrowing.id,
            user.id,
            cond,
            borrowing.penalty_amount or 0.0,
        )
        return borrowing

    return _complete_return_transaction(
        db=db,
        borrowing=borrowing,
        cond=cond,
        notes=notes,
    )


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
    """Kullanıcının ilgili ödünç işlemine ait gecikme cezasını ödediğini veya Admin tarafından tahsil edildiğini işaretler."""
    borrowing = db.get(Borrowing, borrowing_id)
    if not borrowing:
        logger.warning(
            "Ceza ödeme başarısız: Ödünç kaydı bulunamadı -> borrow_id: %s, user_id: %s",
            borrowing_id,
            user.id,
        )
        raise NotFoundError("Ödünç alma kaydı bulunamadı")

    is_admin = any(
        (r.name == RoleName.ADMIN or str(r.name) == "ADMIN") for r in (user.roles or [])
    )
    if borrowing.user_id != user.id and not is_admin:
        logger.warning(
            "Ceza ödeme başarısız: Kayıt kullanıcıya ait değil -> borrow_id: %s, requester: %s, owner: %s",
            borrowing_id,
            user.id,
            borrowing.user_id,
        )
        raise BusinessRuleError("Bu ödünç alma kaydı size ait değil")

    today = date.today()
    if (borrowing.penalty_amount or 0.0) <= 0.0:
        if borrowing.due_date < today:
            overdue_days = (today - borrowing.due_date).days
            borrowing.penalty_amount = round(overdue_days * settings.DAILY_PENALTY_RATE, 2)
        else:
            raise BusinessRuleError("Bu kayıt için ödenecek bir gecikme cezası bulunmamaktadır")

    if borrowing.is_penalty_paid and getattr(borrowing, "penalty_payment_status", "UNPAID") == "PAID":
        raise BusinessRuleError("Bu gecikme cezası zaten yönetici tarafından onaylanmış ve kapatılmıştır")

    now = datetime.now(timezone.utc)
    if is_admin:
        borrowing.penalty_payment_status = "PAID"
        borrowing.is_penalty_paid = True
        borrowing.penalty_paid_at = now
        logger.info(
            "Gecikme cezası Yönetici tarafından tahsil edildi / onaylandı -> borrow_id: %s, user_id: %s, penalty_amount: %.2f TL, is_admin: %s",
            borrowing.id,
            borrowing.user_id,
            borrowing.penalty_amount,
            is_admin,
        )
    else:
        if getattr(borrowing, "penalty_payment_status", "UNPAID") == "PENDING_APPROVAL":
            raise BusinessRuleError(
                "Bu ceza için ödeme bildiriminiz zaten yapılmış olup yönetici onayı beklenmektedir. "
                "Yönetici onaylayana kadar lütfen bekleyiniz."
            )
        borrowing.penalty_payment_status = "PENDING_APPROVAL"
        borrowing.is_penalty_paid = False
        borrowing.penalty_paid_at = now
        logger.info(
            "Kullanıcı ceza ödemesini gerçekleştirdi (Yönetici onayı bekleniyor) -> borrow_id: %s, user_id: %s, penalty_amount: %.2f TL",
            borrowing.id,
            borrowing.user_id,
            borrowing.penalty_amount,
        )

    db.commit()
    db.refresh(borrowing)
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


def cancel_borrow_request(db: Session, user: User, borrowing_id: uuid.UUID) -> Borrowing:
    """Kullanıcının henüz görevli tarafından onaylanmamış (PENDING_BORROW) ödünç talebini iptal eder ve stoğu geri yükler."""
    borrowing = db.get(Borrowing, borrowing_id)
    if not borrowing:
        raise NotFoundError("Ödünç talebi bulunamadı")
    if borrowing.user_id != user.id:
        raise BusinessRuleError("Bu ödünç talebi size ait değil")
    if borrowing.approval_status != "PENDING_BORROW" or borrowing.status == BorrowingStatus.RETURNED:
        raise BusinessRuleError("Yalnızca görevli onayı bekleyen ödünç talepleri iptal edilebilir")

    book = db.get(Book, borrowing.book_id)
    stock_before = int(book.stock_count or 0) if book else 0
    if book:
        book.stock_count = Book.stock_count + 1

    borrowing.approval_status = "REJECTED"
    borrowing.status = BorrowingStatus.RETURNED
    borrowing.return_date = date.today()
    borrowing.admin_notes = "Kullanıcı tarafından ödünç talebi iptal edildi"

    if book:
        db.add(
            StockMovement(
                book_id=book.id,
                user_id=user.id,
                borrowing_id=borrowing.id,
                movement_type="BORROW_REJECTED",
                condition="GOOD",
                quantity_change=1,
                stock_before=stock_before,
                stock_after=stock_before + 1,
                penalty_added=0.0,
                notes="Kullanıcı ödünç talebini iptal etti (+1 stok iade edildi)",
            )
        )

    db.commit()
    if book:
        db.refresh(book)
        sync_reservations(db, book.id)
    db.refresh(borrowing)
    logger.info(
        "Ödünç talebi kullanıcı tarafından iptal edildi -> borrow_id: %s, user_id: %s",
        borrowing.id,
        user.id,
    )
    return borrowing


def admin_approve_borrow(
    db: Session,
    admin_user: User,
    borrowing_id: uuid.UUID,
    admin_notes: str | None = None,
) -> Borrowing:
    """Görevli (ADMIN) bekleyen ödünç talebini (PENDING_BORROW) onaylar ve kitabı teslim eder."""
    borrowing = db.get(Borrowing, borrowing_id)
    if not borrowing:
        raise NotFoundError("Ödünç kaydı bulunamadı")
    if borrowing.status == BorrowingStatus.RETURNED or borrowing.approval_status != "PENDING_BORROW":
        raise BusinessRuleError("Bu kayıt görevli ödünç onayı beklemiyor")

    today = date.today()
    borrowing.approval_status = "APPROVED"
    borrowing.borrow_date = today
    if borrowing.due_date < today:
        borrowing.due_date = today + timedelta(days=14)
    if admin_notes:
        borrowing.admin_notes = admin_notes

    book = db.get(Book, borrowing.book_id)
    cur_stock = int(book.stock_count or 0) if book else 0
    if book:
        db.add(
            StockMovement(
                book_id=book.id,
                user_id=borrowing.user_id,
                admin_id=admin_user.id,
                borrowing_id=borrowing.id,
                movement_type="BORROW_APPROVED",
                condition="GOOD",
                quantity_change=0,
                stock_before=cur_stock,
                stock_after=cur_stock,
                penalty_added=0.0,
                notes=admin_notes or "Ödünç talebi görevli tarafından onaylandı ve kitap üyeye teslim edildi",
            )
        )

    db.commit()
    db.refresh(borrowing)
    logger.info(
        "Ödünç talebi görevli tarafından onaylandı -> borrow_id: %s, user_id: %s, admin_id: %s",
        borrowing.id,
        borrowing.user_id,
        admin_user.id,
    )
    return borrowing


def admin_reject_borrow(
    db: Session,
    admin_user: User,
    borrowing_id: uuid.UUID,
    admin_notes: str | None = None,
) -> Borrowing:
    """Görevli (ADMIN) bekleyen ödünç talebini (PENDING_BORROW) reddeder ve ayrılan stoğu rafa geri ekler."""
    borrowing = db.get(Borrowing, borrowing_id)
    if not borrowing:
        raise NotFoundError("Ödünç kaydı bulunamadı")
    if borrowing.status == BorrowingStatus.RETURNED or borrowing.approval_status != "PENDING_BORROW":
        raise BusinessRuleError("Bu kayıt görevli ödünç onayı beklemiyor")

    book = db.get(Book, borrowing.book_id)
    stock_before = int(book.stock_count or 0) if book else 0
    if book:
        book.stock_count = Book.stock_count + 1

    borrowing.approval_status = "REJECTED"
    borrowing.status = BorrowingStatus.RETURNED
    borrowing.return_date = date.today()
    borrowing.admin_notes = admin_notes or "Ödünç talebi görevli tarafından reddedildi"

    if book:
        db.add(
            StockMovement(
                book_id=book.id,
                user_id=borrowing.user_id,
                admin_id=admin_user.id,
                borrowing_id=borrowing.id,
                movement_type="BORROW_REJECTED",
                condition="GOOD",
                quantity_change=1,
                stock_before=stock_before,
                stock_after=stock_before + 1,
                penalty_added=0.0,
                notes=borrowing.admin_notes,
            )
        )

    db.commit()
    if book:
        db.refresh(book)
        sync_reservations(db, book.id)
    db.refresh(borrowing)
    logger.info(
        "Ödünç talebi görevli tarafından reddedildi ve stok iade edildi -> borrow_id: %s, admin_id: %s",
        borrowing.id,
        admin_user.id,
    )
    return borrowing


def admin_approve_return(
    db: Session,
    admin_user: User,
    borrowing_id: uuid.UUID,
    data: AdminApproveReturnRequest,
) -> Borrowing:
    """Görevli (ADMIN) kitabın fiziksel durumunu (Sağlam / Hasarlı / Kayıp) kontrol ederek iadeyi onaylar."""
    borrowing = db.get(Borrowing, borrowing_id)
    if not borrowing:
        raise NotFoundError("Ödünç kaydı bulunamadı")
    if borrowing.status == BorrowingStatus.RETURNED:
        raise BusinessRuleError("Bu kitap zaten iade edilmiş")
    if borrowing.approval_status == "PENDING_BORROW":
        raise BusinessRuleError("Henüz teslim edilmemiş ödünç talebi iade alınamaz; önce onaylayın veya reddedin")

    return _complete_return_transaction(
        db=db,
        borrowing=borrowing,
        cond=data.return_condition or borrowing.return_condition or "GOOD",
        damage_penalty_override=data.damage_penalty,
        withdraw_override=data.withdraw_from_stock,
        admin_user=admin_user,
        notes=data.admin_notes,
    )


def create_manual_stock_movement(
    db: Session,
    admin_user: User,
    data: StockMovementCreate,
) -> StockMovement:
    """Görevli tarafından doğrudan hasarlı/kayıp kitap stok düşümü veya yeni stok girişi kaydeder."""
    book = db.get(Book, data.book_id)
    if not book:
        raise NotFoundError("Kitap bulunamadı")

    m_type = (data.movement_type or "ADMIN_RESTOCK").upper()
    if m_type not in ("ADMIN_DAMAGE", "ADMIN_LOST", "ADMIN_RESTOCK"):
        raise BusinessRuleError("Geçersiz stok hareket türü (ADMIN_DAMAGE, ADMIN_LOST, ADMIN_RESTOCK olmalıdır)")

    qty = int(data.quantity or 1)
    stock_before = int(book.stock_count or 0)

    if m_type in ("ADMIN_DAMAGE", "ADMIN_LOST"):
        if stock_before < qty:
            raise BusinessRuleError(
                f"Mevcut stok ({stock_before} adet), düşülmek istenen miktardan ({qty} adet) az olamaz"
            )
        book.stock_count = Book.stock_count - qty
        qty_change = -qty
        stock_after = stock_before - qty
        cond = "DAMAGED" if m_type == "ADMIN_DAMAGE" else "LOST"
        default_note = (
            f"Raf/envanter kontrolünde {qty} adet hasarlı kitap tespit edilerek stoktan düşüldü"
            if m_type == "ADMIN_DAMAGE"
            else f"Envanter sayımında {qty} adet kayıp kitap tespit edilerek stoktan düşüldü"
        )
    else:
        book.stock_count = Book.stock_count + qty
        qty_change = qty
        stock_after = stock_before + qty
        cond = "GOOD"
        default_note = f"Envantere {qty} adet yeni/sağlam kitap stoğu eklendi"

    movement = StockMovement(
        book_id=book.id,
        admin_id=admin_user.id,
        movement_type=m_type,
        condition=cond,
        quantity_change=qty_change,
        stock_before=stock_before,
        stock_after=stock_after,
        penalty_added=0.0,
        notes=data.notes or default_note,
    )
    db.add(movement)
    db.commit()
    db.refresh(book)
    sync_reservations(db, book.id)
    db.refresh(movement)
    logger.info(
        "Manuel stok/envanter hareketi kaydedildi -> book_id: %s, type: %s, change: %d, stock_after: %d",
        book.id,
        m_type,
        qty_change,
        stock_after,
    )
    return movement


def _normalize_stock_movement_read(m: StockMovement) -> StockMovementRead:
    item = StockMovementRead.model_validate(m)
    # Eski kayıtlarda RETURN_LOST / RETURN_DAMAGED (rafa dönmeyen) işlemlerde quantity_change=0 kaydedildiyse
    # ödünç alınan nüshanın toplam envanterden -1 kalıcı düşüldüğünü net olarak göster:
    if item.movement_type in ("RETURN_LOST", "RETURN_DAMAGED") and item.quantity_change == 0:
        item.quantity_change = -1
        item.stock_before = item.stock_after + 1
    return item


def get_stock_movements_summary(
    db: Session,
    condition: str | None = None,
    book_id: uuid.UUID | None = None,
    limit: int = 100,
) -> StockMovementSummaryResponse:
    """Tüm stok hareketlerini ve hasar/kayıp raporlarını özet istatistiklerle döndürür."""
    all_movements = list(
        db.scalars(select(StockMovement).order_by(StockMovement.created_at.desc())).all()
    )

    damaged_count = sum(1 for m in all_movements if m.condition == "DAMAGED")
    lost_count = sum(1 for m in all_movements if m.condition == "LOST")
    restock_count = sum(1 for m in all_movements if m.movement_type == "ADMIN_RESTOCK")
    total_comp = round(sum(float(m.penalty_added or 0.0) for m in all_movements), 2)

    filtered = all_movements
    if condition and condition.upper() != "ALL":
        c_up = condition.upper()
        if c_up == "RESTOCK":
            filtered = [m for m in filtered if m.quantity_change > 0]
        else:
            filtered = [m for m in filtered if m.condition == c_up]
    if book_id is not None:
        filtered = [m for m in filtered if m.book_id == book_id]

    items = [_normalize_stock_movement_read(m) for m in filtered[:limit]]
    return StockMovementSummaryResponse(
        total_movements=len(all_movements),
        damaged_reports_count=damaged_count,
        lost_reports_count=lost_count,
        damaged_count=damaged_count,
        lost_count=lost_count,
        restock_count=restock_count,
        total_compensation_amount=total_comp,
        total_damage_lost_penalty=total_comp,
        items=items,
    )


def get_book_history(db: Session, book_id: uuid.UUID) -> BookHistoryResponse:
    """Belirli bir kitabın okuma geçmişini, aktif okuyucularını ve stok/hasar/kayıp hareketlerini döner."""
    book = db.get(Book, book_id)
    if not book:
        raise NotFoundError("Kitap bulunamadı")

    sync_overdue_borrowings(db)

    borrowings = list(
        db.scalars(
            select(Borrowing)
            .where(Borrowing.book_id == book_id)
            .order_by(Borrowing.borrow_date.desc())
        ).all()
    )
    movements = list(
        db.scalars(
            select(StockMovement)
            .where(StockMovement.book_id == book_id)
            .order_by(StockMovement.created_at.desc())
        ).all()
    )

    non_rejected = [b for b in borrowings if b.approval_status != "REJECTED"]
    active_cnt = sum(
        1
        for b in non_rejected
        if b.status != BorrowingStatus.RETURNED and b.approval_status != "PENDING_BORROW"
    )
    pending_cnt = sum(
        1
        for b in borrowings
        if b.status != BorrowingStatus.RETURNED
        and b.approval_status in ("PENDING_BORROW", "PENDING_RETURN")
    )
    returned_cnt = sum(
        1
        for b in non_rejected
        if b.status == BorrowingStatus.RETURNED
    )
    damaged_cnt = sum(1 for m in movements if m.condition == "DAMAGED")
    lost_cnt = sum(1 for m in movements if m.condition == "LOST")
    total_dmg_penalty = round(
        sum(float(b.damage_penalty or 0.0) for b in borrowings), 2
    )

    reading_records: list[BookReadingRecord] = []
    for b in borrowings:
        reader_name = b.user_full_name or "Üye"
        reading_records.append(
            BookReadingRecord(
                borrowing_id=b.id,
                user_id=b.user_id,
                reader_name=reader_name,
                reader_email=b.user_email,
                borrow_date=b.borrow_date,
                due_date=b.due_date,
                return_date=b.return_date,
                status=b.status.value if hasattr(b.status, "value") else str(b.status),
                approval_status=b.approval_status or "APPROVED",
                return_condition=b.return_condition or "GOOD",
                overdue_days=b.overdue_days,
                penalty_amount=float(b.penalty_amount or 0.0),
                damage_penalty=float(b.damage_penalty or 0.0),
                return_notes=b.return_notes,
                admin_notes=b.admin_notes,
            )
        )

    return BookHistoryResponse(
        book_id=book.id,
        book_title=book.title,
        book_isbn=book.isbn,
        current_stock=int(book.stock_count or 0),
        stats=BookHistoryStats(
            total_borrow_count=len(non_rejected),
            active_borrow_count=active_cnt,
            pending_approval_count=pending_cnt,
            returned_count=returned_cnt,
            damaged_count=damaged_cnt,
            lost_count=lost_cnt,
            total_damage_loss_penalty=total_dmg_penalty,
        ),
        reading_history=reading_records,
        stock_movements=[_normalize_stock_movement_read(m) for m in movements],
    )



