import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

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

# --- Book ---
class BookBase(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    isbn: Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=17)]
    published_year: int | None = None
    stock_count: int = Field(default=0, ge=0)

class BookCreate(BookBase):
    publisher_id: uuid.UUID | None = None
    author_ids: list[uuid.UUID] = Field(default_factory=list)
    category_ids: list[int] = Field(default_factory=list)

class BookUpdate(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)] | None = None
    isbn: Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=17)] | None = None
    published_year: int | None = None
    stock_count: int | None = Field(default=None, ge=0)
    publisher_id: uuid.UUID | None = None
    author_ids: list[uuid.UUID] | None = None
    category_ids: list[int] | None = None

class BookRead(BookBase):
    id: uuid.UUID
    publisher: PublisherRead | None = None
    authors: list[AuthorRead] = []
    categories: list[CategoryRead] = []
    reserved_count: int = 0
    reservation_queue_user_ids: list[uuid.UUID] = []
    model_config = ConfigDict(from_attributes=True)

# --- Pagination ---
class PaginatedBooksResponse(BaseModel):
    items: list[BookRead]
    total: int
    page: int
    limit: int
    total_pages: int
