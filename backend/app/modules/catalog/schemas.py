import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

NameStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]

# --- Publisher ---
class PublisherBase(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    contact_info: str | None = None

class PublisherCreate(PublisherBase):
    pass

class PublisherUpdate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)] | None = None
    contact_info: str | None = None

class PublisherRead(PublisherBase):
    id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)

# --- Category ---
class CategoryBase(BaseModel):
    name: NameStr

class CategoryCreate(CategoryBase):
    pass

class CategoryUpdate(CategoryBase):
    pass

class CategoryRead(CategoryBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

# --- Author ---
class AuthorBase(BaseModel):
    first_name: NameStr
    last_name: NameStr

class AuthorCreate(AuthorBase):
    pass

class AuthorUpdate(BaseModel):
    first_name: NameStr | None = None
    last_name: NameStr | None = None

class AuthorRead(AuthorBase):
    id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)

# --- Book Copy Info ---
class BookCopyInfo(BaseModel):
    copy_number: int
    copy_code: str
    barcode: str
    status: str
    status_label: str
    borrower_name: str | None = None
    due_date: date | None = None
    borrowing_id: uuid.UUID | None = None

    model_config = ConfigDict(from_attributes=True)


# --- Book ---
class BookBase(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    isbn: Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=17)]
    published_year: int | None = None
    stock_count: int = Field(default=0, ge=0)
    call_number: str | None = None
    cover_url: str | None = None

class BookCreate(BookBase):
    publisher_id: uuid.UUID | None = None
    author_ids: list[uuid.UUID] = Field(default_factory=list)
    category_ids: list[int] = Field(default_factory=list)

class BookUpdate(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)] | None = None
    isbn: Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=17)] | None = None
    published_year: int | None = None
    stock_count: int | None = Field(default=None, ge=0)
    call_number: str | None = None
    cover_url: str | None = None
    publisher_id: uuid.UUID | None = None
    author_ids: list[uuid.UUID] | None = None
    category_ids: list[int] | None = None

class BookRead(BookBase):
    id: uuid.UUID
    call_number: str | None = None
    publisher: PublisherRead | None = None
    authors: list[AuthorRead] = []
    categories: list[CategoryRead] = []
    reserved_count: int = 0
    reservation_queue_user_ids: list[uuid.UUID] = []
    active_reservation_expires_at: datetime | None = None
    copies: list[BookCopyInfo] = []
    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def compute_call_number_if_missing(self) -> "BookRead":
        if not self.call_number and self.title:
            try:
                from app.modules.catalog.call_number import generate_dewey_call_number

                primary_author = self.authors[0].name if self.authors else None
                self.call_number = generate_dewey_call_number(
                    categories=self.categories,
                    author_name=primary_author,
                    title=self.title,
                    published_year=self.published_year,
                )
            except Exception:
                self.call_number = f"800 / GEN-{self.published_year or 2026}"
        return self

# --- ISBN Lookup ---
class IsbnLookupResponse(BaseModel):
    title: str = Field(..., description="Kitap başlığı")
    isbn: str = Field(..., description="Sorgulanan ISBN")
    published_year: int | None = Field(None, description="Yayın yılı")
    cover_url: str | None = Field(None, description="Kitap kapağı görsel adresi")
    publisher_id: uuid.UUID | None = Field(None, description="Eşleşen veya yeni oluşturulan yayınevi kimliği")
    publisher_name: str | None = Field(None, description="Yayınevi adı")
    author_ids: list[uuid.UUID] = Field(default_factory=list, description="Eşleşen veya yeni oluşturulan yazar kimlikleri")
    author_names: list[str] = Field(default_factory=list, description="Yazar adları")
    category_ids: list[int] = Field(default_factory=list, description="Eşleşen veya yeni oluşturulan kategori kimlikleri")
    category_names: list[str] = Field(default_factory=list, description="Kategori adları")

# --- Pagination ---
class PaginatedBooksResponse(BaseModel):
    items: list[BookRead]
    total: int
    page: int
    limit: int
    total_pages: int
