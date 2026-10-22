import math
import uuid
from typing import Any, Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.catalog.models import Author, Book, Category, Publisher
from app.modules.catalog.schemas import (
    AuthorCreate,
    AuthorUpdate,
    BookCreate,
    BookUpdate,
    CategoryCreate,
    CategoryUpdate,
    PublisherCreate,
    PublisherUpdate,
)


class NotFoundError(Exception):
    pass


class DuplicateError(Exception):
    pass


# --- Publisher ---
def get_publishers(db: Session) -> Sequence[Publisher]:
    return db.scalars(select(Publisher)).all()


def get_publisher(db: Session, publisher_id: uuid.UUID) -> Publisher:
    db_obj = db.get(Publisher, publisher_id)
    if not db_obj:
        raise NotFoundError("Yayınevi bulunamadı")
    return db_obj


def create_publisher(db: Session, data: PublisherCreate) -> Publisher:
    db_obj = Publisher(**data.model_dump())
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def update_publisher(db: Session, publisher_id: uuid.UUID, data: PublisherUpdate) -> Publisher:
    db_obj = get_publisher(db, publisher_id)
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_obj, key, value)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def delete_publisher(db: Session, publisher_id: uuid.UUID) -> None:
    db_obj = get_publisher(db, publisher_id)
    db.delete(db_obj)
    db.commit()


# --- Category ---
def get_categories(db: Session) -> Sequence[Category]:
    return db.scalars(select(Category)).all()


def get_category(db: Session, category_id: int) -> Category:
    db_obj = db.get(Category, category_id)
    if not db_obj:
        raise NotFoundError("Kategori bulunamadı")
    return db_obj


def create_category(db: Session, data: CategoryCreate) -> Category:
    db_obj = Category(**data.model_dump())
    db.add(db_obj)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise DuplicateError("Bu kategori adı zaten mevcut")
    db.refresh(db_obj)
    return db_obj


def update_category(db: Session, category_id: int, data: CategoryUpdate) -> Category:
    db_obj = get_category(db, category_id)
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_obj, key, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise DuplicateError("Bu kategori adı zaten mevcut")
    db.refresh(db_obj)
    return db_obj


def delete_category(db: Session, category_id: int) -> None:
    db_obj = get_category(db, category_id)
    db.delete(db_obj)
    db.commit()


# --- Author ---
def get_authors(db: Session) -> Sequence[Author]:
    return db.scalars(select(Author)).all()


def get_author(db: Session, author_id: uuid.UUID) -> Author:
    db_obj = db.get(Author, author_id)
    if not db_obj:
        raise NotFoundError("Yazar bulunamadı")
    return db_obj


def create_author(db: Session, data: AuthorCreate) -> Author:
    db_obj = Author(**data.model_dump())
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def update_author(db: Session, author_id: uuid.UUID, data: AuthorUpdate) -> Author:
    db_obj = get_author(db, author_id)
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_obj, key, value)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def delete_author(db: Session, author_id: uuid.UUID) -> None:
    db_obj = get_author(db, author_id)
    db.delete(db_obj)
    db.commit()


# --- Book ---
def get_books(
    db: Session,
    page: int = 1,
    limit: int = 10,
    search: str | None = None,
    category: str | None = None,
    author: str | None = None,
    publisher: str | None = None,
    sort_by: str = "title",
    sort_order: str = "asc",
) -> dict[str, Any]:
    from app.modules.borrowing.service import sync_reservations

    sync_reservations(db)
    stmt = select(Book)

    # 1. Arama (Search): Başlıkta (title) büyük/küçük harf duyarsız arama
    if search:
        stmt = stmt.where(Book.title.ilike(f"%{search.strip()}%"))

    # 2. Filtreleme (Filtering - AND zinciri)
    if category:
        stmt = stmt.where(Book.categories.any(Category.name.ilike(f"%{category.strip()}%")))

    if author:
        author_term = f"%{author.strip()}%"
        stmt = stmt.where(
            Book.authors.any(
                or_(
                    Author.first_name.ilike(author_term),
                    Author.last_name.ilike(author_term),
                    func.concat(Author.first_name, " ", Author.last_name).ilike(author_term),
                )
            )
        )

    if publisher:
        stmt = stmt.where(Book.publisher.has(Publisher.name.ilike(f"%{publisher.strip()}%")))

    # Toplam kayıt sayısını (total) hesaplama (filtreler dahil)
    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = db.scalar(count_stmt) or 0

    # 3. Sıralama (Sorting)
    sort_map = {
        "title": Book.title,
        "published_year": Book.published_year,
        "stock_count": Book.stock_count,
        "isbn": Book.isbn,
    }
    sort_column = sort_map.get(sort_by.lower(), Book.title)
    if sort_order.lower() == "desc":
        stmt = stmt.order_by(sort_column.desc())
    else:
        stmt = stmt.order_by(sort_column.asc())

    # 4. Sayfalama (Pagination)
    offset = (page - 1) * limit
    stmt = stmt.offset(offset).limit(limit)

    items = db.scalars(stmt).all()
    total_pages = math.ceil(total / limit) if total > 0 else 0

    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
    }


def get_book(db: Session, book_id: uuid.UUID) -> Book:
    from app.modules.borrowing.service import sync_reservations

    sync_reservations(db, book_id)
    db_obj = db.get(Book, book_id)
    if not db_obj:
        raise NotFoundError("Kitap bulunamadı")
    return db_obj


def create_book(db: Session, data: BookCreate) -> Book:
    db_obj = Book(
        title=data.title,
        isbn=data.isbn,
        published_year=data.published_year,
        stock_count=data.stock_count,
        publisher_id=data.publisher_id,
    )

    # Çoktan çoğa ilişki atamaları
    if data.author_ids:
        db_obj.authors = db.scalars(select(Author).where(Author.id.in_(data.author_ids))).all()
    if data.category_ids:
        db_obj.categories = db.scalars(select(Category).where(Category.id.in_(data.category_ids))).all()

    db.add(db_obj)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise DuplicateError("Bu ISBN veya Kural ihlali (Mevcut değil/Stok<0) olabilir")

    db.refresh(db_obj)
    return db_obj


def update_book(db: Session, book_id: uuid.UUID, data: BookUpdate) -> Book:
    from app.modules.borrowing.service import sync_reservations

    db_obj = get_book(db, book_id)

    update_data = data.model_dump(exclude_unset=True, exclude={"author_ids", "category_ids"})
    for key, value in update_data.items():
        setattr(db_obj, key, value)

    if data.author_ids is not None:
        db_obj.authors = db.scalars(select(Author).where(Author.id.in_(data.author_ids))).all()
    if data.category_ids is not None:
        db_obj.categories = db.scalars(select(Category).where(Category.id.in_(data.category_ids))).all()

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise DuplicateError("Bu ISBN zaten mevcut")

    # Kitap stoğu güncellendiyse (ör. 0'dan 1'e çıktıysa) sırada bekleyen rezervasyonun 24 saatlik süresini başlat
    sync_reservations(db, book_id)
    db.refresh(db_obj)
    return db_obj


def delete_book(db: Session, book_id: uuid.UUID) -> None:
    db_obj = get_book(db, book_id)
    db.delete(db_obj)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise DuplicateError("Bu kitap başka bir kayıt tarafından kullanıldığı için silinemez")
