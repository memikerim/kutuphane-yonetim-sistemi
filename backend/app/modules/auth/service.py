"""Auth iş mantığı. HTTP'den bağımsızdır; hatalar domain exception olarak fırlatılır."""

import logging
from datetime import date
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    hash_password,
    verify_dummy_password,
    verify_password,
)
from app.modules.auth.models import Role, RoleName, User
from app.modules.auth.schemas import TokenResponse, UserAlertItem, UserRead, UserRegister

logger = logging.getLogger(__name__)


class EmailAlreadyRegisteredError(Exception):
    """Kayıt sırasında e-posta zaten kullanılıyorsa fırlatılır."""


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))


def get_or_create_role(db: Session, name: RoleName) -> Role:
    role = db.scalar(select(Role).where(Role.name == name))
    if role is None:  # Seed migration çalışmamışsa bile sistem çalışmaya devam etsin
        role = Role(name=name)
        db.add(role)
        db.flush()
    return role


def register_user(db: Session, data: UserRegister) -> User:
    if get_user_by_email(db, data.email) is not None:
        logger.warning("Kullanıcı kaydı başarısız: E-posta zaten kayıtlı -> %s", data.email)
        raise EmailAlreadyRegisteredError

    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        first_name=data.first_name,
        last_name=data.last_name,
        roles=[get_or_create_role(db, RoleName.USER)],  # varsayılan rol
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        # Aynı anda gelen iki kayıt isteğinde unique constraint son savunma hattıdır
        db.rollback()
        logger.warning("Kullanıcı kaydı çakışması (race condition) -> %s", data.email)
        raise EmailAlreadyRegisteredError from exc
    db.refresh(user)
    logger.info("Yeni kullanıcı başarıyla kaydedildi -> email: %s, user_id: %s", user.email, user.id)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """Bilgiler doğruysa kullanıcıyı, değilse None döner."""
    user = get_user_by_email(db, email)
    if user is None:
        verify_dummy_password(password)
        logger.warning("Başarısız giriş denemesi: Kullanıcı bulunamadı -> email: %s", email)
        return None
    if not verify_password(password, user.password_hash):
        logger.warning("Başarısız giriş denemesi: Hatalı şifre -> email: %s", email)
        return None
    logger.info("Kullanıcı kimlik doğrulaması başarılı -> email: %s, user_id: %s", user.email, user.id)
    return user


def issue_access_token(user: User) -> TokenResponse:
    token = create_access_token(
        user_id=user.id,
        email=user.email,
        roles=[role.name.value for role in user.roles],
    )
    logger.info("Kullanıcı için access token üretildi -> user_id: %s, email: %s", user.id, user.email)
    return TokenResponse(
        access_token=token, expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


def build_user_read_with_alerts(db: Session, user: User) -> UserRead:
    """Kullanıcının ban durumunu, gecikmiş kitaplarını ve ödenmemiş gecikme/hasar/kayıp borçlarını hesaplar."""
    from app.modules.borrowing.models import Borrowing, BorrowingStatus
    from app.modules.borrowing.service import sync_overdue_borrowings

    sync_overdue_borrowings(db, user.id)
    today = date.today()

    borrowings = list(
        db.scalars(
            select(Borrowing)
            .where(Borrowing.user_id == user.id)
            .order_by(Borrowing.due_date.asc())
        ).all()
    )

    overdue_books_count = 0
    unpaid_overdue_total = 0.0
    unpaid_damage_loss_total = 0.0
    unpaid_penalty_total = 0.0
    pending_penalty_approval_count = 0
    alert_items: list[UserAlertItem] = []

    for b in borrowings:
        cond = (b.return_condition or "GOOD").upper()
        approval_st = b.approval_status or "APPROVED"
        payment_st = getattr(b, "penalty_payment_status", "UNPAID")
        if b.status != BorrowingStatus.RETURNED and approval_st == "PENDING_BORROW":
            continue

        due_d = b.due_date.date() if hasattr(b.due_date, "date") else b.due_date
        is_overdue_active = (
            b.status != BorrowingStatus.RETURNED
            and (b.status == BorrowingStatus.OVERDUE or (due_d is not None and today > due_d))
        )
        is_damaged_or_lost_pending = (
            b.status != BorrowingStatus.RETURNED and cond in ("DAMAGED", "LOST")
        )
        has_unpaid_penalty = (
            ((b.penalty_amount or 0.0) > 0 or (b.damage_penalty or 0.0) > 0)
            and not b.is_penalty_paid
        )

        if not (is_overdue_active or is_damaged_or_lost_pending or has_unpaid_penalty):
            continue

        if payment_st == "PENDING_APPROVAL":
            pending_penalty_approval_count += 1

        if b.status != BorrowingStatus.RETURNED and is_overdue_active:
            overdue_books_count += 1

        overdue_days = int(b.overdue_days or 0)
        if is_overdue_active and overdue_days <= 0 and due_d is not None:
            overdue_days = max(1, (today - due_d).days)

        dmg_pen = float(b.damage_penalty or 0.0)
        if dmg_pen <= 0.0 and cond == "DAMAGED":
            dmg_pen = float(settings.DAMAGED_BOOK_PENALTY)
        elif dmg_pen <= 0.0 and cond == "LOST":
            dmg_pen = float(settings.LOST_BOOK_PENALTY)

        overdue_pen = round(overdue_days * settings.DAILY_PENALTY_RATE, 2)
        total_pen = float(b.penalty_amount or 0.0)
        if total_pen < round(overdue_pen + dmg_pen, 2):
            total_pen = round(overdue_pen + dmg_pen, 2)

        if not b.is_penalty_paid:
            unpaid_overdue_total += overdue_pen
            unpaid_damage_loss_total += dmg_pen
            unpaid_penalty_total += total_pen

        alert_items.append(
            UserAlertItem(
                borrowing_id=b.id,
                book_id=b.book_id,
                book_title=b.book.title if b.book else "Kitap",
                due_date=due_d,
                status=b.status.value if hasattr(b.status, "value") else str(b.status),
                approval_status=approval_st,
                return_condition=cond,
                overdue_days=overdue_days,
                overdue_penalty=round(overdue_pen, 2),
                damage_penalty=round(dmg_pen, 2),
                penalty_amount=round(total_pen, 2),
                penalty_payment_status=payment_st,
                is_penalty_paid=bool(b.is_penalty_paid),
            )
        )

    base = UserRead.model_validate(user)
    base.overdue_books_count = overdue_books_count
    base.unpaid_overdue_total = round(unpaid_overdue_total, 2)
    base.unpaid_damage_loss_total = round(unpaid_damage_loss_total, 2)
    base.unpaid_penalty_total = round(unpaid_penalty_total, 2)
    base.pending_penalty_approval_count = pending_penalty_approval_count
    base.alert_items = alert_items
    return base
