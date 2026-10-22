import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.modules.auth.models import User
    from app.modules.catalog.models import Book


class Review(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "reviews"
    __table_args__ = (
        # Kural: bir kullanıcı bir kitaba yalnızca bir yorum yapabilir
        UniqueConstraint("user_id", "book_id", name="uq_reviews_user_book"),
        # Kural: puan 1-5 arası
        CheckConstraint("rating BETWEEN 1 AND 5", name="rating_range"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    book_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)

    user: Mapped["User"] = relationship(back_populates="reviews", lazy="selectin")
    book: Mapped["Book"] = relationship(back_populates="reviews")

    @property
    def user_full_name(self) -> str | None:
        return f"{self.user.first_name} {self.user.last_name}" if self.user else None


