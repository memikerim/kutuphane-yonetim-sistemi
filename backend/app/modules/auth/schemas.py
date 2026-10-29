import uuid
from datetime import date, datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator

from app.modules.auth.models import RoleName

NameStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]

PASSWORD_MIN_LENGTH = 8
BCRYPT_MAX_BYTES = 72  # bcrypt 72 byte'tan sonrasını yok sayar


class UserRegister(BaseModel):
    first_name: NameStr
    last_name: NameStr
    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=BCRYPT_MAX_BYTES)

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "first_name": "Ali",
                    "last_name": "Yılmaz",
                    "email": "ali@kutuphane.com",
                    "password": "Sifre1234",
                }
            ]
        }
    )

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value.encode("utf-8")) > BCRYPT_MAX_BYTES:
            raise ValueError(f"Şifre en fazla {BCRYPT_MAX_BYTES} byte olabilir")
        if not any(c.isalpha() for c in value) or not any(c.isdigit() for c in value):
            raise ValueError("Şifre en az bir harf ve bir rakam içermelidir")
        return value


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=BCRYPT_MAX_BYTES)

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"email": "ali@kutuphane.com", "password": "Sifre1234"}]}
    )

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Token geçerlilik süresi (saniye)")


class UserAlertItem(BaseModel):
    borrowing_id: uuid.UUID
    book_id: uuid.UUID
    book_title: str
    due_date: date
    status: str
    approval_status: str = "APPROVED"
    return_condition: str = "GOOD"
    overdue_days: int = 0
    overdue_penalty: float = 0.0
    damage_penalty: float = 0.0
    penalty_amount: float = 0.0


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    created_at: datetime
    roles: list[RoleName]
    is_banned: bool = False
    ban_reason: str | None = None
    banned_at: datetime | None = None
    overdue_books_count: int = 0
    unpaid_overdue_total: float = 0.0
    unpaid_damage_loss_total: float = 0.0
    unpaid_penalty_total: float = 0.0
    alert_items: list[UserAlertItem] = Field(default_factory=list)

    @field_validator("roles", mode="before")
    @classmethod
    def roles_to_names(cls, value: Any) -> list[Any]:
        # ORM'den Role nesneleri gelir -> isimlerine çevir
        return [getattr(role, "name", role) for role in value]
