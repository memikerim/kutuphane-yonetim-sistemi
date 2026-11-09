import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.modules.auth.models import User
    from app.modules.catalog.models import Book


class LibraryStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class MembershipRole(str, enum.Enum):
    MEMBER = "MEMBER"
    LIBRARY_ADMIN = "LIBRARY_ADMIN"


class MembershipStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    BANNED = "BANNED"


class Library(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "libraries"

    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=LibraryStatus.PENDING.value, server_default="PENDING"
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    daily_fine_amount: Mapped[float] = mapped_column(
        Float, nullable=False, default=5.0, server_default="5.0"
    )
    max_borrow_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=14, server_default="14"
    )
    max_books_per_user: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3, server_default="3"
    )
    penalty_rules_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        default="Ödünç alınan kitapların süresi içinde sağlam olarak iade edilmesi zorunludur. Gecikme halinde günlük gecikme cezası uygulanır.",
    )

    created_by: Mapped["User | None"] = relationship(
        foreign_keys=[created_by_id], lazy="selectin"
    )
    memberships: Mapped[list["LibraryMembership"]] = relationship(
        back_populates="library", cascade="all, delete-orphan"
    )
    books: Mapped[list["Book"]] = relationship(back_populates="library")

    @property
    def created_by_name(self) -> str | None:
        if self.created_by:
            return f"{self.created_by.first_name} {self.created_by.last_name}"
        return None

    @property
    def created_by_email(self) -> str | None:
        if self.created_by:
            return self.created_by.email
        return None

    def __repr__(self) -> str:
        return f"<Library {self.name} ({self.status})>"


class LibraryMembership(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "library_memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "library_id", name="uq_user_library_membership"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    library_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("libraries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(
        String(30), nullable=False, default=MembershipRole.MEMBER.value, server_default="MEMBER"
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=MembershipStatus.PENDING.value, server_default="PENDING"
    )
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    identity_or_student_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    department_or_address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    application_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ban_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    user: Mapped["User"] = relationship(back_populates="library_memberships", lazy="selectin")
    library: Mapped["Library"] = relationship(back_populates="memberships", lazy="selectin")

    @property
    def user_full_name(self) -> str | None:
        return f"{self.user.first_name} {self.user.last_name}" if self.user else None

    @property
    def user_email(self) -> str | None:
        return self.user.email if self.user else None

    @property
    def library_name(self) -> str | None:
        return self.library.name if self.library else None

    @property
    def library_daily_fine_amount(self) -> float:
        return float(self.library.daily_fine_amount) if self.library else 5.0

    @property
    def library_max_borrow_days(self) -> int:
        return int(self.library.max_borrow_days) if self.library else 14

    @property
    def library_max_books_per_user(self) -> int:
        return int(self.library.max_books_per_user) if self.library else 3

    @property
    def library_penalty_rules_text(self) -> str | None:
        return self.library.penalty_rules_text if self.library else None

    def __repr__(self) -> str:
        return f"<LibraryMembership user={self.user_id} lib={self.library_id} role={self.role} status={self.status}>"

