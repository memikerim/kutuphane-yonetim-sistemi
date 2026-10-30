import enum
import uuid
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Enum, Float, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.modules.auth.models import User
    from app.modules.catalog.models import Book


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class BorrowingStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    RETURNED = "RETURNED"
    OVERDUE = "OVERDUE"


class ReservationStatus(str, enum.Enum):
    PENDING = "PENDING"
    FULFILLED = "FULFILLED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class Borrowing(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "borrowings"
    __table_args__ = (
        CheckConstraint("due_date >= borrow_date", name="due_after_borrow"),
        CheckConstraint(
            "return_date IS NULL OR return_date >= borrow_date", name="return_after_borrow"
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    book_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("books.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    borrow_date: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=func.current_date()
    )
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    return_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[BorrowingStatus] = mapped_column(
        Enum(BorrowingStatus, name="borrowing_status", native_enum=False, length=20),
        nullable=False,
        default=BorrowingStatus.ACTIVE,
        server_default=BorrowingStatus.ACTIVE.value,
    )
    penalty_amount: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0.0"
    )
    is_penalty_paid: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    penalty_payment_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="UNPAID", server_default="UNPAID"
    )
    penalty_paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approval_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="APPROVED", server_default="APPROVED"
    )
    return_condition: Mapped[str] = mapped_column(
        String(20), nullable=False, default="GOOD", server_default="GOOD"
    )
    damage_penalty: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0.0"
    )
    return_notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    admin_notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    copy_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_rejection_read: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    user: Mapped["User"] = relationship(back_populates="borrowings", lazy="selectin")
    book: Mapped["Book"] = relationship(back_populates="borrowings", lazy="selectin")

    @property
    def overdue_days(self) -> int:
        from app.core.config import settings

        if self.status == BorrowingStatus.RETURNED:
            if self.return_date and self.due_date and self.return_date > self.due_date:
                return (self.return_date - self.due_date).days
            overdue_part = max(0.0, float(self.penalty_amount or 0.0) - float(self.damage_penalty or 0.0))
            if overdue_part > 0 and settings.DAILY_PENALTY_RATE > 0:
                return int(round(overdue_part / settings.DAILY_PENALTY_RATE))
            return 0
        if self.approval_status == "PENDING_BORROW":
            return 0
        today = date.today()
        if self.due_date and today > self.due_date:
            return (today - self.due_date).days
        return 0

    @property
    def user_email(self) -> str | None:
        return self.user.email if self.user else None

    @property
    def user_full_name(self) -> str | None:
        return f"{self.user.first_name} {self.user.last_name}" if self.user else None

    @property
    def book_title(self) -> str | None:
        return self.book.title if self.book else None

    @property
    def book_isbn(self) -> str | None:
        return self.book.isbn if self.book else None

    @property
    def book_cover_url(self) -> str | None:
        return self.book.cover_url if self.book else None

    @property
    def book_author(self) -> str | None:
        if self.book and getattr(self.book, "authors", None):
            return ", ".join(a.name for a in self.book.authors)
        return None

    @property
    def user_is_banned(self) -> bool:
        return bool(getattr(self.user, "is_banned", False)) if self.user else False

    @property
    def user_ban_reason(self) -> str | None:
        return getattr(self.user, "ban_reason", None) if self.user else None

    @property
    def call_number(self) -> str | None:
        if self.book:
            return getattr(self.book, "computed_call_number", None) or getattr(self.book, "call_number", None)
        return None

    @property
    def assigned_copy_code(self) -> str:
        if self.copy_code:
            return self.copy_code
        if self.book and getattr(self.book, "isbn", None):
            try:
                from app.modules.catalog.call_number import format_copy_code

                return format_copy_code(self.book.isbn, 1)
            except Exception:
                pass
        return "DEM-GEN-K1"



class Reservation(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "reservations"
    __table_args__ = (
        # Kural: aynı kullanıcı aynı kitap için yalnızca 1 adet PENDING rezervasyona sahip olabilir.
        # Partial unique index -> geçmişteki CANCELLED/FULFILLED kayıtlar engellenmez.
        Index(
            "uq_reservations_user_book_pending",
            "user_id",
            "book_id",
            unique=True,
            postgresql_where=text("status = 'PENDING'"),
            sqlite_where=text("status = 'PENDING'"),
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    book_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reservation_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    status: Mapped[ReservationStatus] = mapped_column(
        Enum(ReservationStatus, name="reservation_status", native_enum=False, length=20),
        nullable=False,
        default=ReservationStatus.PENDING,
        server_default=ReservationStatus.PENDING.value,
    )

    user: Mapped["User"] = relationship(back_populates="reservations")
    book: Mapped["Book"] = relationship(back_populates="reservations", lazy="selectin")

    @property
    def remaining_seconds(self) -> int | None:
        if self.expires_at is None:
            return None
        diff = (_ensure_utc(self.expires_at) - datetime.now(timezone.utc)).total_seconds()
        return max(0, int(diff))

    @property
    def queue_position(self) -> int:
        if not self.book or not self.book.reservations:
            return 1
        pending = [
            r for r in self.book.reservations if r.status == ReservationStatus.PENDING
        ]
        pending.sort(
            key=lambda r: (
                _ensure_utc(r.reservation_date).timestamp() if r.reservation_date else 0.0,
                str(r.id),
            )
        )
        for idx, r in enumerate(pending):
            if r.id == self.id:
                return idx + 1
        return 1

    @property
    def people_ahead(self) -> int:
        return max(0, self.queue_position - 1)

    @property
    def can_borrow_now(self) -> bool:
        if not self.book or self.book.stock_count <= 0:
            return False
        return self.queue_position <= self.book.stock_count

    @property
    def turn_starts_at(self) -> datetime | None:
        """
        Eğer kitap stokta varsa (stock_count > 0) ancak sıra henüz bu kullanıcıya
        gelmemişse (queue_position > stock_count), öndeki kullanıcı(lar) ödünç almazsa
        bu kullanıcının 24 saatlik süresinin otomatik başlayacağı kesin tarihi döner.
        """
        from datetime import timedelta

        if self.can_borrow_now or not self.book or (self.book.stock_count or 0) <= 0:
            return None
        if not self.book.reservations:
            return None

        stock = self.book.stock_count
        pending = [
            r for r in self.book.reservations if r.status == ReservationStatus.PENDING
        ]
        pending.sort(
            key=lambda r: (
                _ensure_utc(r.reservation_date).timestamp() if r.reservation_date else 0.0,
                str(r.id),
            )
        )

        my_idx: int | None = None
        for idx, r in enumerate(pending):
            if r.id == self.id:
                my_idx = idx
                break

        if my_idx is None or my_idx < stock:
            return None

        active_expirations = sorted(
            [
                _ensure_utc(r.expires_at)
                for r in pending[:stock]
                if r.expires_at is not None
            ]
        )
        if not active_expirations:
            return None

        slot_idx = (my_idx - stock) % len(active_expirations)
        cycles = (my_idx - stock) // len(active_expirations)
        return active_expirations[slot_idx] + timedelta(hours=24 * cycles)

    @property
    def queue_message(self) -> str:
        pos = self.queue_position
        if self.can_borrow_now:
            return (
                f"Rezerve listesinde {pos}. sıradasınız (Sıra sizde!). "
                "Kitap stoğu sizin için ayrıldı; giriş yapmanıza gerek kalmadan başlayan 24 saatlik süreniz dolmadan ödünç alabilirsiniz."
            )
        if pos > 1:
            if self.book and (self.book.stock_count or 0) > 0:
                return (
                    f"Rezerve listesinde {pos}. sıradasınız. "
                    "Önünüzdeki kullanıcının 24 saatlik süresi bittiği anda (giriş yapmanıza gerek olmadan) sizin 24 saatlik süreniz otomatik başlar."
                )
            return (
                f"Rezerve listesinde {pos}. sıradasınız. "
                "Kitap stoğa girip önünüzdeki kullanıcıların sırası tamamlandığı anda 24 saatlik süreniz otomatik başlar."
            )
        return (
            "Rezerve listesinde 1. sıradasınız. "
            "Kitap ödünç alınma stoğuna girdiği anda (giriş yapmanıza gerek olmadan) 24 saatlik ödünç alma süreniz otomatik başlar."
        )


class StockMovement(UUIDPrimaryKeyMixin, Base):
    """Kitap stok hareketleri, fiziksel durum kontrolleri, hasar ve kayıp raporları."""

    __tablename__ = "stock_movements"

    book_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    admin_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    borrowing_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("borrowings.id", ondelete="SET NULL"), nullable=True
    )
    movement_type: Mapped[str] = mapped_column(
        String(40), nullable=False, default="RETURN_GOOD"
    )
    condition: Mapped[str] = mapped_column(
        String(20), nullable=False, default="GOOD"
    )
    quantity_change: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stock_before: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stock_after: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    penalty_added: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    book: Mapped["Book"] = relationship(lazy="selectin")
    user: Mapped["User | None"] = relationship(foreign_keys=[user_id], lazy="selectin")
    admin: Mapped["User | None"] = relationship(foreign_keys=[admin_id], lazy="selectin")

    @property
    def book_title(self) -> str | None:
        return self.book.title if self.book else None

    @property
    def book_isbn(self) -> str | None:
        return self.book.isbn if self.book else None

    @property
    def book_cover_url(self) -> str | None:
        return self.book.cover_url if self.book else None

    @property
    def book_author(self) -> str | None:
        if self.book and getattr(self.book, "authors", None):
            return ", ".join(a.name for a in self.book.authors)
        return None

    @property
    def user_is_banned(self) -> bool:
        return bool(getattr(self.user, "is_banned", False)) if self.user else False

    @property
    def user_ban_reason(self) -> str | None:
        return getattr(self.user, "ban_reason", None) if self.user else None

    @property
    def call_number(self) -> str | None:
        if self.book:
            return getattr(self.book, "computed_call_number", None) or getattr(self.book, "call_number", None)
        return None

    @property
    def assigned_copy_code(self) -> str:
        if self.copy_code:
            return self.copy_code
        if self.book and getattr(self.book, "isbn", None):
            try:
                from app.modules.catalog.call_number import format_copy_code

                return format_copy_code(self.book.isbn, 1)
            except Exception:
                pass
        return "DEM-GEN-K1"

    @property
    def user_full_name(self) -> str | None:
        return f"{self.user.first_name} {self.user.last_name}" if self.user else None

    @property
    def user_email(self) -> str | None:
        return self.user.email if self.user else None

    @property
    def admin_full_name(self) -> str | None:
        return f"{self.admin.first_name} {self.admin.last_name}" if self.admin else None



