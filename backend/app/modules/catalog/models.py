import uuid
from typing import Any, TYPE_CHECKING

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
    call_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cover_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    publisher: Mapped[Publisher | None] = relationship(back_populates="books", lazy="joined")
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

    @property
    def active_reservation_expires_at(self):
        from app.modules.borrowing.models import _ensure_utc

        if not self.stock_count or self.stock_count <= 0:
            return None
        pending = self._sorted_pending_reservations[: self.stock_count]
        expirations = [
            _ensure_utc(r.expires_at) for r in pending if r.expires_at is not None
        ]
        return min(expirations) if expirations else None

    @property
    def computed_call_number(self) -> str:
        if self.call_number:
            return self.call_number
        try:
            from app.modules.catalog.call_number import generate_dewey_call_number

            author_name = self.authors[0].full_name if self.authors else None
            return generate_dewey_call_number(
                categories=self.categories,
                author_name=author_name,
                title=self.title,
                published_year=self.published_year,
            )
        except Exception:
            return f"800 / GEN-{self.published_year or 2026}"

    @property
    def copies(self) -> list[dict]:
        try:
            import re
            from app.modules.catalog.call_number import format_barcode, format_copy_code

            active_borrows = []
            if self.borrowings:
                for b in self.borrowings:
                    is_active = (b.return_date is None) and (
                        getattr(b.status, "value", str(b.status)) in ("ACTIVE", "OVERDUE")
                        or getattr(b, "approval_status", "APPROVED") in ("PENDING_BORROW", "PENDING_RETURN")
                    )
                    if is_active:
                        active_borrows.append(b)

            assigned_by_code: dict[str, Any] = {}
            unassigned_borrows = []
            for b in active_borrows:
                c_code = getattr(b, "copy_code", None)
                if c_code:
                    assigned_by_code[c_code] = b
                else:
                    unassigned_borrows.append(b)

            current_stock = max(0, int(self.stock_count or 0))
            total_copies_count = len(active_borrows) + current_stock
            if total_copies_count == 0 and current_stock == 0:
                total_copies_count = 1

            max_seen_num = 0
            for code in assigned_by_code.keys():
                m = re.search(r"-K(\d+)$", code)
                if m:
                    max_seen_num = max(max_seen_num, int(m.group(1)))

            total_copies = max(total_copies_count, max_seen_num)

            copy_list = []
            for i in range(1, total_copies + 1):
                code = format_copy_code(self.isbn, i)
                barcode = format_barcode(self.isbn, i)

                borrowing = assigned_by_code.get(code)
                if not borrowing and unassigned_borrows:
                    borrowing = unassigned_borrows.pop(0)

                if borrowing:
                    appr_st = getattr(borrowing, "approval_status", "APPROVED")
                    st_val = getattr(borrowing.status, "value", str(borrowing.status))
                    if appr_st == "PENDING_BORROW":
                        st = "PENDING_BORROW"
                        st_label = "Teslim Onayı Bekliyor"
                    elif appr_st == "PENDING_RETURN":
                        st = "PENDING_RETURN"
                        st_label = "İade Kontrolü Bekliyor"
                    elif st_val == "OVERDUE":
                        st = "OVERDUE"
                        st_label = "Gecikmede (Ödünç)"
                    else:
                        st = "BORROWED"
                        st_label = "Ödünç Verildi"

                    b_name = getattr(borrowing, "user_full_name", None)
                    b_due = getattr(borrowing, "due_date", None)
                    b_id = getattr(borrowing, "id", None)
                else:
                    st = "AVAILABLE"
                    st_label = "Rafta (Müsait)"
                    b_name = None
                    b_due = None
                    b_id = None

                copy_list.append(
                    {
                        "copy_number": i,
                        "copy_code": code,
                        "barcode": barcode,
                        "status": st,
                        "status_label": st_label,
                        "borrower_name": b_name,
                        "due_date": b_due,
                        "borrowing_id": b_id,
                    }
                )

            return copy_list
        except Exception:
            return []

    def __repr__(self) -> str:
        return f"<Book {self.isbn} - {self.title}>"


