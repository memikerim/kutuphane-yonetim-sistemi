import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.database import DbSession
from app.modules.auth.dependencies import require_roles
from app.modules.auth.models import RoleName
from app.modules.catalog import service
from app.modules.catalog.schemas import (
    AuthorCreate,
    AuthorRead,
    AuthorUpdate,
    BookCreate,
    BookRead,
    BookUpdate,
    CategoryCreate,
    CategoryRead,
    CategoryUpdate,
    IsbnLookupResponse,
    PaginatedBooksResponse,
    PublisherCreate,
    PublisherRead,
    PublisherUpdate,
)

# Ana bir router tanımı, prefix kullanmıyoruz ki alt uç noktalar direkt /api/v1/... olsun (main.py hallediyor)
router = APIRouter(tags=["Catalog"])

# Tüm yazma işlemleri için ortak Admin dependency
AdminDep = Annotated[None, Depends(require_roles([RoleName.ADMIN]))]


def handle_service_error(func, *args, **kwargs):
    """Domain hatalarını HTTP cevaplarına çevirir."""
    try:
        return func(*args, **kwargs)
    except service.NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except service.DuplicateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


# --- Publisher Endpoints ---
@router.get("/publishers", response_model=list[PublisherRead], summary="Yayınevlerini listele")
def get_publishers(db: DbSession):
    return service.get_publishers(db)


@router.get("/publishers/{id}", response_model=PublisherRead, summary="Yayınevi detay")
def get_publisher(id: uuid.UUID, db: DbSession):
    return handle_service_error(service.get_publisher, db, id)


@router.post("/publishers", response_model=PublisherRead, status_code=status.HTTP_201_CREATED, summary="Yayınevi ekle (ADMIN)")
def create_publisher(data: PublisherCreate, db: DbSession, admin: AdminDep):
    return service.create_publisher(db, data)


@router.put("/publishers/{id}", response_model=PublisherRead, summary="Yayınevi güncelle (ADMIN)")
def update_publisher(id: uuid.UUID, data: PublisherUpdate, db: DbSession, admin: AdminDep):
    return handle_service_error(service.update_publisher, db, id, data)


@router.delete("/publishers/{id}", status_code=status.HTTP_204_NO_CONTENT, summary="Yayınevi sil (ADMIN)")
def delete_publisher(id: uuid.UUID, db: DbSession, admin: AdminDep):
    handle_service_error(service.delete_publisher, db, id)


# --- Category Endpoints ---
@router.get("/categories", response_model=list[CategoryRead], summary="Kategorileri listele")
def get_categories(db: DbSession):
    return service.get_categories(db)


@router.get("/categories/{id}", response_model=CategoryRead, summary="Kategori detay")
def get_category(id: int, db: DbSession):
    return handle_service_error(service.get_category, db, id)


@router.post("/categories", response_model=CategoryRead, status_code=status.HTTP_201_CREATED, summary="Kategori ekle (ADMIN)")
def create_category(data: CategoryCreate, db: DbSession, admin: AdminDep):
    return handle_service_error(service.create_category, db, data)


@router.put("/categories/{id}", response_model=CategoryRead, summary="Kategori güncelle (ADMIN)")
def update_category(id: int, data: CategoryUpdate, db: DbSession, admin: AdminDep):
    return handle_service_error(service.update_category, db, id, data)


@router.delete("/categories/{id}", status_code=status.HTTP_204_NO_CONTENT, summary="Kategori sil (ADMIN)")
def delete_category(id: int, db: DbSession, admin: AdminDep):
    handle_service_error(service.delete_category, db, id)


# --- Author Endpoints ---
@router.get("/authors", response_model=list[AuthorRead], summary="Yazarları listele")
def get_authors(db: DbSession):
    return service.get_authors(db)


@router.get("/authors/{id}", response_model=AuthorRead, summary="Yazar detay")
def get_author(id: uuid.UUID, db: DbSession):
    return handle_service_error(service.get_author, db, id)


@router.post("/authors", response_model=AuthorRead, status_code=status.HTTP_201_CREATED, summary="Yazar ekle (ADMIN)")
def create_author(data: AuthorCreate, db: DbSession, admin: AdminDep):
    return service.create_author(db, data)


@router.put("/authors/{id}", response_model=AuthorRead, summary="Yazar güncelle (ADMIN)")
def update_author(id: uuid.UUID, data: AuthorUpdate, db: DbSession, admin: AdminDep):
    return handle_service_error(service.update_author, db, id, data)


@router.delete("/authors/{id}", status_code=status.HTTP_204_NO_CONTENT, summary="Yazar sil (ADMIN)")
def delete_author(id: uuid.UUID, db: DbSession, admin: AdminDep):
    handle_service_error(service.delete_author, db, id)


# --- Book Endpoints ---
@router.get("/books", response_model=PaginatedBooksResponse, summary="Kitapları listele, ara, filtrele ve sayfala")
def get_books(
    db: DbSession,
    page: int = Query(1, ge=1, description="Sayfa numarası"),
    limit: int = Query(10, ge=1, le=100, description="Sayfa başına kayıt sayısı"),
    search: str | None = Query(None, description="Kitap başlığında arama"),
    category: str | None = Query(None, description="Kategori adına göre filtreleme"),
    author: str | None = Query(None, description="Yazar adına göre filtreleme"),
    publisher: str | None = Query(None, description="Yayınevi adına göre filtreleme"),
    sortBy: str = Query("title", description="Sıralanacak alan (title, published_year, stock_count, isbn)"),
    sortOrder: str = Query("asc", pattern="^(asc|desc)$", description="Sıralama yönü (asc, desc)"),
):
    return service.get_books(
        db=db,
        page=page,
        limit=limit,
        search=search,
        category=category,
        author=author,
        publisher=publisher,
        sort_by=sortBy,
        sort_order=sortOrder,
    )


@router.get(
    "/books/lookup-isbn/{isbn}",
    response_model=IsbnLookupResponse,
    summary="ISBN ile otomatik kitap bilgisi sorgula ve eksikleri oluştur (ADMIN)",
    description=(
        "OpenLibrary ve Google Books API kullanarak ISBN sorgular. "
        "Yazar, yayınevi veya kategoriler veritabanında henüz yoksa otomatik olarak oluşturur "
        "ve frontend formunu doldurmaya hazır JSON döner."
    ),
)
def lookup_isbn(isbn: str, db: DbSession, admin: AdminDep):
    return handle_service_error(service.lookup_isbn_data, db, isbn)


@router.get("/books/{id}", response_model=BookRead, summary="Kitap detay")
def get_book(id: uuid.UUID, db: DbSession):
    return handle_service_error(service.get_book, db, id)


@router.post("/books", response_model=BookRead, status_code=status.HTTP_201_CREATED, summary="Kitap ekle (ADMIN)")
def create_book(data: BookCreate, db: DbSession, admin: AdminDep):
    return handle_service_error(service.create_book, db, data)


@router.put("/books/{id}", response_model=BookRead, summary="Kitap güncelle (ADMIN)")
def update_book(id: uuid.UUID, data: BookUpdate, db: DbSession, admin: AdminDep):
    return handle_service_error(service.update_book, db, id, data)


@router.delete("/books/{id}", status_code=status.HTTP_204_NO_CONTENT, summary="Kitap sil (ADMIN)")
def delete_book(id: uuid.UUID, db: DbSession, admin: AdminDep):
    handle_service_error(service.delete_book, db, id)
