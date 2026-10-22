import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.modules.borrowing.models import Borrowing, Reservation
    from app.modules.review.models import Review


# BookAuthors: (book_id, author_id) composite PK - çoktan çoğa
book_authors = Table(
    "book_authors",
    Base.metadata,
    Column("book_id", ForeignKey("books.id", ondelete="CASCADE"), primary_key=True),
    Column("author_id", ForeignKey("authors.id", ondelete="CASCADE"), primary_key=True),
)

# BookCategories: (book_id, category_id) composite PK - çoktan çoğa
book_categories = Table(
    "book_categories",
    Base.metadata,
    Column("book_id", ForeignKey("books.id", ondelete="CASCADE"), primary_key=True),
    Column("category_id", ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True),
)


class Publisher(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "publishers"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_info: Mapped[str | None] = mapped_column(Text)

    books: Mapped[list["Book"]] = relationship(back_populates="publisher")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    books: Mapped[list["Book"]] = relationship(
        secondary=book_categories, back_populates="categories"
    )


class Author(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "authors"

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)

    books: Mapped[list["Book"]] = relationship(secondary=book_authors, back_populates="authors")


class Book(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "books"
    __table_args__ = (
        # Kural: stok negatif olamaz
        CheckConstraint("stock_count >= 0", name="stock_count_non_negative"),
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    isbn: Mapped[str] = mapped_column(String(17), unique=True, nullable=False)  # ISBN-13 + tireler
    publisher_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("publishers.id", ondelete="SET NULL"), index=True
    )
    published_year: Mapped[int | None] = mapped_column(SmallInteger)
    stock_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    publisher: Mapped[Publisher | None] = relationship(back_populates="books")
    authors: Mapped[list[Author]] = relationship(
        secondary=book_authors, back_populates="books", lazy="selectin"
    )
    categories: Mapped[list[Category]] = relationship(
        secondary=book_categories, back_populates="books", lazy="selectin"
    )
    borrowings: Mapped[list["Borrowing"]] = relationship(back_populates="book")
    reservations: Mapped[list["Reservation"]] = relationship(
        back_populates="book", lazy="selectin"
    )
    reviews: Mapped[list["Review"]] = relationship(back_populates="book")

    @property
    def _sorted_pending_reservations(self) -> list["Reservation"]:
        from app.modules.borrowing.models import _ensure_utc

        if not self.reservations:
            return []
        pending = [r for r in self.reservations if r.status.value == "PENDING"]
        pending.sort(
            key=lambda r: (
                _ensure_utc(r.reservation_date).timestamp() if r.reservation_date else 0.0,
                str(r.id),
            )
        )
        return pending

    @property
    def reserved_count(self) -> int:
        return len(self._sorted_pending_reservations)

    @property
    def reservation_queue_user_ids(self) -> list[uuid.UUID]:
        return [r.user_id for r in self._sorted_pending_reservations]

    def __repr__(self) -> str:
        return f"<Book {self.isbn} - {self.title}>"


