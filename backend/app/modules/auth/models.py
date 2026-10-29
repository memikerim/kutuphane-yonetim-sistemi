import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.modules.borrowing.models import Borrowing, Reservation
    from app.modules.review.models import Review


class RoleName(str, enum.Enum):
    USER = "USER"
    ADMIN = "ADMIN"


# UserRoles: (user_id, role_id) composite primary key
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


class User(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ban_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    banned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    roles: Mapped[list["Role"]] = relationship(
        secondary=user_roles, back_populates="users", lazy="selectin"
    )
    borrowings: Mapped[list["Borrowing"]] = relationship(back_populates="user")
    reservations: Mapped[list["Reservation"]] = relationship(back_populates="user")
    reviews: Mapped[list["Review"]] = relationship(back_populates="user")

    def __repr__(self) -> str:
        return f"<User {self.email}>"


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[RoleName] = mapped_column(
        Enum(RoleName, name="role_name", native_enum=False, length=20),
        unique=True,
        nullable=False,
    )

    users: Mapped[list[User]] = relationship(secondary=user_roles, back_populates="roles")

    def __repr__(self) -> str:
        return f"<Role {self.name}>"


__all__ = ["User", "Role", "RoleName", "user_roles"]
