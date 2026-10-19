import enum
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, DateTime, Enum, ForeignKey, Index, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.modules.auth.models import User
    from app.modules.catalog.models import Book


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
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    status: Mapped[ReservationStatus] = mapped_column(
        Enum(ReservationStatus, name="reservation_status", native_enum=False, length=20),
        nullable=False,
        default=ReservationStatus.PENDING,
        server_default=ReservationStatus.PENDING.value,
    )

    user: Mapped["User"] = relationship(back_populates="reservations")
    book: Mapped["Book"] = relationship(back_populates="reservations")

