import enum
import uuid
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, DateTime, Enum, ForeignKey, Index, func, text
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

    user: Mapped["User"] = relationship(back_populates="borrowings")
    book: Mapped["Book"] = relationship(back_populates="borrowings")


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
    def queue_message(self) -> str:
        pos = self.queue_position
        if self.can_borrow_now:
            return (
                f"Rezerve listesinde {pos}. sıradasınız (Sıra sizde!). "
                "Kitap stoğu sizin için ayrıldı, 24 saatlik süreniz dolmadan ödünç alabilirsiniz."
            )
        if pos > 1:
            return (
                f"Rezerve listesinde {pos}. sıradasınız. "
                "Diğer kullanıcılar süreleri bitene kadar ödünç almazlarsa ödünç alabilirsiniz."
            )
        return (
            "Rezerve listesinde 1. sıradasınız. "
            "Kitap stoğu çıktığı anda 24 saatlik ödünç alma süreniz başlayacaktır."
        )


