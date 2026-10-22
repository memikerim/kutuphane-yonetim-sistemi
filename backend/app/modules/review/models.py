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
    reactions: Mapped[list["ReviewReaction"]] = relationship(
        back_populates="review", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def user_full_name(self) -> str | None:
        return f"{self.user.first_name} {self.user.last_name}" if self.user else None

    @property
    def likes_count(self) -> int:
        return sum(1 for r in (self.reactions or []) if r.value == 1)

    @property
    def dislikes_count(self) -> int:
        return sum(1 for r in (self.reactions or []) if r.value == -1)

    @property
    def liked_user_ids(self) -> list[uuid.UUID]:
        return [r.user_id for r in (self.reactions or []) if r.value == 1]

    @property
    def disliked_user_ids(self) -> list[uuid.UUID]:
        return [r.user_id for r in (self.reactions or []) if r.value == -1]


class ReviewReaction(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "review_reactions"
    __table_args__ = (
        UniqueConstraint("review_id", "user_id", name="uq_review_reactions_review_user"),
        CheckConstraint("value IN (1, -1)", name="ck_review_reactions_value"),
    )

    review_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    value: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    review: Mapped["Review"] = relationship(back_populates="reactions")



