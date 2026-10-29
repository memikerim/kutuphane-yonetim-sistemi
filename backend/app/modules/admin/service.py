from datetime import date, datetime, timezone
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.admin.schemas import (
    AdminUserItem,
    UnpaidPenaltiesResponse,
    UnpaidPenaltyItem,
)
from app.modules.auth.models import RoleName, User
from app.modules.borrowing.models import Borrowing, BorrowingStatus
from app.modules.borrowing.service import BusinessRuleError, NotFoundError, sync_overdue_borrowings

logger = logging.getLogger(__name__)


def _to_date(val: date | datetime | None) -> date | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.date()
    return val


def get_unpaid_penalties(db: Session) -> UnpaidPenaltiesResponse:
    """
    Hem iade edilmiş ama cezası henüz ödenmemiş kayıtları hem de şu an teslim tarihi
    geçmiş aktif (OVERDUE) veya hasar/kayıp bildirimi yapılmış ödünçlerden doğan güncel borçları döndürür.
    """
    sync_overdue_borrowings(db)
    today = date.today()

    stmt = select(Borrowing).order_by(Borrowing.due_date.asc())
    all_borrowings = db.scalars(stmt).all()

    items: list[UnpaidPenaltyItem] = []
    total_unpaid = 0.0

    for b in all_borrowings:
        penalty = 0.0
        overdue_days = 0
        user_banned = bool(getattr(b.user, "is_banned", False)) if b.user else False
        user_ban_note = getattr(b.user, "ban_reason", None) if b.user else None

        if b.status == BorrowingStatus.RETURNED:
            # İade edilmiş ama cezası ödenmemiş
            if (b.penalty_amount or 0.0) > 0.0 and not b.is_penalty_paid:
                penalty = float(b.penalty_amount)
                overdue_days = b.overdue_days
                total_unpaid += penalty
                items.append(
                    UnpaidPenaltyItem(
                        borrowing_id=b.id,
                        user_id=b.user_id,
                        user_full_name=f"{b.user.first_name} {b.user.last_name}" if b.user else "Bilinmiyor",
                        user_email=b.user.email if b.user else "Bilinmiyor",
                        user_is_banned=user_banned,
                        user_ban_reason=user_ban_note,
                        book_id=b.book_id,
                        book_title=b.book.title if b.book else "Bilinmiyor",
                        borrow_date=_to_date(b.borrow_date),
                        due_date=_to_date(b.due_date),
                        return_date=_to_date(b.return_date),
                        status="RETURNED",
                        return_condition=b.return_condition or "GOOD",
                        damage_penalty=float(b.damage_penalty or 0.0),
                        overdue_days=max(0, overdue_days),
                        penalty_amount=penalty,
                        is_penalty_paid=False,
                    )
                )
        else:
            if b.approval_status == "PENDING_BORROW":
                continue
            due_d = _to_date(b.due_date)
            cond = (b.return_condition or "GOOD").upper()
            is_overdue = b.status == BorrowingStatus.OVERDUE or (due_d is not None and today > due_d)
            has_damage_or_loss = cond in ("DAMAGED", "LOST") or float(b.damage_penalty or 0.0) > 0
            if (is_overdue or has_damage_or_loss) and not b.is_penalty_paid:
                overdue_days = (
                    b.overdue_days or (max(1, (today - due_d).days) if (is_overdue and due_d) else 0)
                )
                dmg_pen = float(b.damage_penalty or 0.0)
                if dmg_pen <= 0.0 and cond == "DAMAGED":
                    dmg_pen = float(settings.DAMAGED_BOOK_PENALTY)
                elif dmg_pen <= 0.0 and cond == "LOST":
                    dmg_pen = float(settings.LOST_BOOK_PENALTY)
                penalty = round(overdue_days * settings.DAILY_PENALTY_RATE + dmg_pen, 2)
                total_unpaid += penalty
                items.append(
                    UnpaidPenaltyItem(
                        borrowing_id=b.id,
                        user_id=b.user_id,
                        user_full_name=f"{b.user.first_name} {b.user.last_name}" if b.user else "Bilinmiyor",
                        user_email=b.user.email if b.user else "Bilinmiyor",
                        user_is_banned=user_banned,
                        user_ban_reason=user_ban_note,
                        book_id=b.book_id,
                        book_title=b.book.title if b.book else "Bilinmiyor",
                        borrow_date=_to_date(b.borrow_date),
                        due_date=due_d,
                        return_date=None,
                        status="OVERDUE" if is_overdue else "RETURNED",
                        return_condition=cond,
                        damage_penalty=dmg_pen,
                        overdue_days=overdue_days,
                        penalty_amount=penalty,
                        is_penalty_paid=False,
                    )
                )

    return UnpaidPenaltiesResponse(
        total_unpaid_amount=round(total_unpaid, 2),
        debtor_count=len(items),
        items=items,
    )


def _build_admin_user_item(db: Session, u: User) -> AdminUserItem:
    today = date.today()
    borrowings = list(
        db.scalars(select(Borrowing).where(Borrowing.user_id == u.id)).all()
    )
    active_cnt = 0
    overdue_cnt = 0
    unpaid_total = 0.0

    for b in borrowings:
        cond = (b.return_condition or "GOOD").upper()
        due_d = _to_date(b.due_date)
        if b.status != BorrowingStatus.RETURNED:
            if b.approval_status != "PENDING_BORROW":
                active_cnt += 1
                if b.status == BorrowingStatus.OVERDUE or (due_d is not None and today > due_d):
                    overdue_cnt += 1

        if not b.is_penalty_paid:
            overdue_days = int(b.overdue_days or 0)
            if (
                b.status != BorrowingStatus.RETURNED
                and b.approval_status != "PENDING_BORROW"
                and due_d is not None
                and today > due_d
                and overdue_days <= 0
            ):
                overdue_days = max(1, (today - due_d).days)
            dmg_pen = float(b.damage_penalty or 0.0)
            if dmg_pen <= 0.0 and cond == "DAMAGED":
                dmg_pen = float(settings.DAMAGED_BOOK_PENALTY)
            elif dmg_pen <= 0.0 and cond == "LOST":
                dmg_pen = float(settings.LOST_BOOK_PENALTY)
            calc_pen = round(overdue_days * settings.DAILY_PENALTY_RATE + dmg_pen, 2)
            pen = max(float(b.penalty_amount or 0.0), calc_pen)
            if pen > 0:
                unpaid_total += pen

    return AdminUserItem(
        id=u.id,
        email=u.email,
        first_name=u.first_name,
        last_name=u.last_name,
        full_name=f"{u.first_name} {u.last_name}",
        roles=[r.name.value if hasattr(r.name, "value") else str(r.name) for r in (u.roles or [])],
        is_banned=bool(getattr(u, "is_banned", False)),
        ban_reason=getattr(u, "ban_reason", None),
        banned_at=getattr(u, "banned_at", None),
        active_borrowings_count=active_cnt,
        overdue_books_count=overdue_cnt,
        unpaid_penalty_total=round(unpaid_total, 2),
        created_at=u.created_at,
    )


def list_users_for_admin(db: Session) -> list[AdminUserItem]:
    sync_overdue_borrowings(db)
    users = list(db.scalars(select(User).order_by(User.created_at.desc())).all())
    return [_build_admin_user_item(db, u) for u in users]


def ban_user(
    db: Session,
    admin_user: User,
    target_user_id: uuid.UUID,
    ban_reason: str,
) -> AdminUserItem:
    target = db.get(User, target_user_id)
    if not target:
        raise NotFoundError("Kullanıcı bulunamadı")
    if target.id == admin_user.id:
        raise BusinessRuleError("Kendi yönetici hesabınızı banlayamazsınız")
    is_target_admin = any(
        (r.name == RoleName.ADMIN or str(r.name) == "ADMIN") for r in (target.roles or [])
    )
    if is_target_admin:
        raise BusinessRuleError("Başka bir ADMIN (Yönetici) hesabını banlayamazsınız")

    reason_clean = (ban_reason or "").strip() or (
        "Kitap iadeniz ve gecikme/hasar ödemeniz yapılana kadar hesabınız yeni kitap ödünç almaya, "
        "rezervasyon yapmaya ve yorum yapmaya kapalı olacaktır."
    )
    target.is_banned = True
    target.ban_reason = reason_clean
    target.banned_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(target)
    logger.warning(
        "Kullanıcı yönetici tarafından banlandı (kısıtlandı) -> target_user: %s (%s), admin: %s, reason: %s",
        target.email,
        target.id,
        admin_user.email,
        reason_clean,
    )
    return _build_admin_user_item(db, target)


def unban_user(
    db: Session,
    admin_user: User,
    target_user_id: uuid.UUID,
) -> AdminUserItem:
    target = db.get(User, target_user_id)
    if not target:
        raise NotFoundError("Kullanıcı bulunamadı")

    target.is_banned = False
    target.ban_reason = None
    target.banned_at = None
    db.commit()
    db.refresh(target)
    logger.info(
        "Kullanıcının banı (hesap kısıtlaması) yönetici tarafından kaldırıldı -> target_user: %s (%s), admin: %s",
        target.email,
        target.id,
        admin_user.email,
    )
    return _build_admin_user_item(db, target)

