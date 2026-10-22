import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ReviewReactionCreate(BaseModel):
    value: Literal[1, -1] = Field(
        ...,
        description="1: Beğen / Faydalı Buldum (Thumbs Up), -1: Beğenme / Katılmıyorum (Thumbs Down)",
    )



class ReviewCreate(BaseModel):
    book_id: uuid.UUID = Field(..., description="Değerlendirilen kitabın benzersiz kimliği (UUID)")
    rating: int = Field(..., ge=1, le=5, description="Kitaba verilen puan (1 ile 5 arasında)")
    comment: str | None = Field(
        None,
        max_length=2000,
        description="Kullanıcının kitap hakkındaki yorumu (opsiyonel)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "book_id": "a3bb189e-8bf9-3888-9912-ace4e6543002",
                "rating": 5,
                "comment": "Akıcı ve ufuk açıcı bir eser. Kesinlikle tavsiye ederim.",
            }
        }
    )


class ReviewRead(BaseModel):
    id: uuid.UUID = Field(..., description="Yorumun benzersiz kimliği")
    user_id: uuid.UUID = Field(..., description="Yorumu yapan kullanıcının kimliği")
    user_full_name: str | None = Field(None, description="Yorumu yapan kullanıcının adı soyadı")
    book_id: uuid.UUID = Field(..., description="Kitabın benzersiz kimliği")
    rating: int = Field(..., ge=1, le=5, description="Verilen puan (1-5)")
    comment: str | None = Field(None, description="Yorum metni")
    likes_count: int = Field(0, description="Beğeni / Faydalı (Thumbs Up) sayısı")
    dislikes_count: int = Field(0, description="Beğenmeme / Faydasız (Thumbs Down) sayısı")
    liked_user_ids: list[uuid.UUID] = Field(
        default_factory=list, description="Bu yorumu beğenen kullanıcıların ID listesi"
    )
    disliked_user_ids: list[uuid.UUID] = Field(
        default_factory=list, description="Bu yorumu beğenmeyen kullanıcıların ID listesi"
    )
    created_at: datetime = Field(..., description="Yorumun oluşturulma tarihi")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "c1f7b020-f561-4547-8a39-652a083f2a33",
                "user_id": "7d4b2df2-7db5-4b2e-a3da-3f5f65a1e5a8",
                "book_id": "a3bb189e-8bf9-3888-9912-ace4e6543002",
                "rating": 5,
                "comment": "Akıcı ve ufuk açıcı bir eser. Kesinlikle tavsiye ederim.",
                "created_at": "2026-10-11T13:30:00Z",
            }
        },
    )
