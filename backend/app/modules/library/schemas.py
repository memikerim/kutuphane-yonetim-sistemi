import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

LibraryNameStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]


class LibraryBase(BaseModel):
    name: LibraryNameStr
    description: str | None = Field(default=None, max_length=2000)
    daily_fine_amount: float = Field(default=5.0, ge=0.0, le=10000.0, description="Günlük gecikme cezası (TL)")
    max_borrow_days: int = Field(default=14, ge=1, le=365, description="Maksimum ödünç alma süresi (Gün)")
    max_books_per_user: int = Field(default=3, ge=1, le=50, description="Kişi başı maksimum aktif kitap limiti")
    penalty_rules_text: str | None = Field(
        default="Ödünç alınan kitapların süresi içinde sağlam olarak iade edilmesi zorunludur. Gecikme halinde günlük gecikme cezası uygulanır.",
        max_length=4000,
        description="Kütüphanenin özel ceza ve ödünç şartları metni",
    )


class LibraryCreate(LibraryBase):
    pass


class LibrarySettingsUpdate(BaseModel):
    name: LibraryNameStr | None = None
    description: str | None = Field(default=None, max_length=2000)
    daily_fine_amount: float | None = Field(default=None, ge=0.0, le=10000.0)
    max_borrow_days: int | None = Field(default=None, ge=1, le=365)
    max_books_per_user: int | None = Field(default=None, ge=1, le=50)
    penalty_rules_text: str | None = Field(default=None, max_length=4000)


class LibraryStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(APPROVED|REJECTED)$", description="APPROVED veya REJECTED")


class LibraryRead(LibraryBase):
    id: uuid.UUID
    status: str
    created_by_id: uuid.UUID | None = None
    created_by_name: str | None = None
    created_by_email: str | None = None
    created_at: datetime
    book_count: int = 0
    member_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class LibraryCreateResponse(BaseModel):
    message: str
    library: LibraryRead


class LibraryMembershipApplyRequest(BaseModel):
    library_id: uuid.UUID | None = Field(default=None, description="Başvurulacak kütüphane ID'si")
    library_name: str | None = Field(default=None, max_length=200, description="Başvurulacak kütüphane adı (ID yerine isimle başvuru için)")
    phone: str = Field(..., min_length=3, max_length=50, description="Telefon Numarası")
    identity_or_student_no: str = Field(..., min_length=2, max_length=100, description="Öğrenci / Kurum / TC Kimlik No")
    department_or_address: str = Field(..., min_length=2, max_length=300, description="Bölüm / Birim veya Adres Bilgisi")
    application_note: str | None = Field(default=None, max_length=500, description="Katılım Notu (İsteğe bağlı)")


class LibraryMembershipStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(APPROVED|REJECTED|BANNED)$", description="APPROVED, REJECTED veya BANNED")
    ban_reason: str | None = Field(default=None, max_length=500)


class LibraryMembershipRoleUpdate(BaseModel):
    role: str = Field(..., pattern="^(MEMBER|LIBRARY_ADMIN)$", description="MEMBER veya LIBRARY_ADMIN")
    confirmed: bool = Field(
        default=True,
        description="Yönetici yetkisi verme onay uyarısının kabul edildiğini doğrular",
    )


class LibraryMembershipRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    user_full_name: str | None = None
    user_email: str | None = None
    library_id: uuid.UUID
    library_name: str | None = None
    library_daily_fine_amount: float = 5.0
    library_max_borrow_days: int = 14
    library_max_books_per_user: int = 3
    library_penalty_rules_text: str | None = None
    role: str
    status: str
    phone: str | None = None
    identity_or_student_no: str | None = None
    department_or_address: str | None = None
    application_note: str | None = None
    ban_reason: str | None = None
    created_at: datetime
    active_borrowings_count: int = 0
    overdue_books_count: int = 0
    unpaid_penalty_total: float = 0.0

    model_config = ConfigDict(from_attributes=True)

