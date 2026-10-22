import logging
import math
import re
import uuid
from typing import Any, Sequence

import httpx
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

logger = logging.getLogger(__name__)


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
        cover_url=data.cover_url,
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


def lookup_isbn_data(db: Session, raw_isbn: str) -> dict[str, Any]:
    """ISBN sorgulama servisi (OpenLibrary & Google Books API).

    Eğer API'den gelen Yazar, Yayınevi veya Kategori veritabanında yoksa
    otomatik olarak oluşturulur ve ID'leri ile birlikte kitap oluşturma
    şablonuna uygun olarak döndürülür.
    """
    clean_isbn = re.sub(r"[^0-9Xx]", "", raw_isbn).upper()
    if not clean_isbn:
        raise NotFoundError("Geçersiz veya boş ISBN numarası")

    title = None
    published_year = None
    cover_url = None
    raw_authors: list[str] = []
    raw_publisher: str | None = None
    raw_categories: list[str] = []

    # 1. OpenLibrary API Sorgulama
    openlibrary_url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{clean_isbn}&format=json&jscmd=data"
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(openlibrary_url)
            if resp.status_code == 200:
                data = resp.json()
                key = f"ISBN:{clean_isbn}"
                if key in data:
                    book_info = data[key]
                    title = book_info.get("title")

                    # Yayın yılı ayrıştırma
                    pub_date = book_info.get("publish_date", "")
                    year_match = re.search(r"\b(1\d{3}|20\d{2})\b", str(pub_date))
                    if year_match:
                        published_year = int(year_match.group(1))

                    # Kapak görseli
                    cover = book_info.get("cover", {})
                    cover_url = cover.get("large") or cover.get("medium") or cover.get("small")
                    if not cover_url:
                        cover_url = f"https://covers.openlibrary.org/b/isbn/{clean_isbn}-L.jpg"

                    # Yazarlar
                    for a in book_info.get("authors", []):
                        if isinstance(a, dict) and a.get("name"):
                            raw_authors.append(a["name"].strip())

                    # Yayınevi
                    for p in book_info.get("publishers", []):
                        if isinstance(p, dict) and p.get("name") and not raw_publisher:
                            raw_publisher = p["name"].strip()

                    # Kategoriler / Konular
                    for s in book_info.get("subjects", [])[:5]:
                        s_name = s.get("name") if isinstance(s, dict) else str(s)
                        if s_name and len(s_name) <= 50:
                            raw_categories.append(s_name.strip())
    except Exception as e:
        logger.warning("OpenLibrary API isteği sırasında hata: %s", e)

    # 2. Google Books API Yedek Sorgulama (OpenLibrary'de bulunamazsa)
    if not title:
        google_url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{clean_isbn}"
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(google_url)
                if resp.status_code == 200:
                    g_data = resp.json()
                    items = g_data.get("items", [])
                    if items:
                        volume = items[0].get("volumeInfo", {})
                        title = volume.get("title")

                        pub_date = volume.get("publishedDate", "")
                        year_match = re.search(r"\b(1\d{3}|20\d{2})\b", str(pub_date))
                        if year_match:
                            published_year = int(year_match.group(1))

                        img_links = volume.get("imageLinks", {})
                        g_cover = (
                            img_links.get("extraLarge")
                            or img_links.get("large")
                            or img_links.get("medium")
                            or img_links.get("thumbnail")
                        )
                        if g_cover:
                            cover_url = g_cover.replace("http://", "https://")

                        for a in volume.get("authors", []):
                            if a:
                                raw_authors.append(a.strip())

                        if volume.get("publisher"):
                            raw_publisher = volume["publisher"].strip()

                        for c in volume.get("categories", [])[:5]:
                            if c:
                                raw_categories.append(c.strip())
        except Exception as e:
            logger.warning("Google Books API isteği sırasında hata: %s", e)

    if not title:
        raise NotFoundError("Bu ISBN ile kitap bulunamadı")

    # Akıllı Eşleştirme ve Veritabanı Otomasyonu:
    # A) Yayınevi
    publisher_id = None
    if raw_publisher:
        pub_obj = db.scalar(
            select(Publisher).where(func.lower(Publisher.name) == raw_publisher.lower())
        )
        if not pub_obj:
            pub_obj = Publisher(name=raw_publisher)
            db.add(pub_obj)
            db.commit()
            db.refresh(pub_obj)
        publisher_id = pub_obj.id

    # B) Yazarlar
    author_ids = []
    author_names = []
    for a_name in raw_authors:
        parts = a_name.strip().split()
        if len(parts) == 1:
            first_name = parts[0]
            last_name = "-"
        else:
            last_name = parts[-1]
            first_name = " ".join(parts[:-1])

        auth_obj = db.scalar(
            select(Author).where(
                func.lower(Author.first_name) == first_name.lower(),
                func.lower(Author.last_name) == last_name.lower(),
            )
        )
        if not auth_obj:
            auth_obj = Author(first_name=first_name, last_name=last_name)
            db.add(auth_obj)
            db.commit()
            db.refresh(auth_obj)

        if auth_obj.id not in author_ids:
            author_ids.append(auth_obj.id)
            author_names.append(f"{auth_obj.first_name} {auth_obj.last_name}")

    # C) Kategoriler
    category_ids = []
    category_names = []
    for c_name in raw_categories:
        clean_c_name = c_name[:100].strip()
        if not clean_c_name:
            continue
        cat_obj = db.scalar(
            select(Category).where(func.lower(Category.name) == clean_c_name.lower())
        )
        if not cat_obj:
            cat_obj = Category(name=clean_c_name)
            db.add(cat_obj)
            try:
                db.commit()
                db.refresh(cat_obj)
            except IntegrityError:
                db.rollback()
                cat_obj = db.scalar(
                    select(Category).where(func.lower(Category.name) == clean_c_name.lower())
                )

        if cat_obj and cat_obj.id not in category_ids:
            category_ids.append(cat_obj.id)
            category_names.append(cat_obj.name)

    return {
        "title": title,
        "isbn": raw_isbn.strip(),
        "published_year": published_year,
        "cover_url": cover_url,
        "publisher_id": publisher_id,
        "publisher_name": raw_publisher,
        "author_ids": author_ids,
        "author_names": author_names,
        "category_ids": category_ids,
        "category_names": category_names,
    }

