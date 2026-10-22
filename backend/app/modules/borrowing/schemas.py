import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.borrowing.models import BorrowingStatus, ReservationStatus

# --- Borrowing ---
class BorrowingCreate(BaseModel):
    book_id: uuid.UUID
    due_date: date = Field(description="İade edilmesi gereken son tarih")

class BorrowingRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    book_id: uuid.UUID
    borrow_date: date
    due_date: date
    return_date: date | None = None
    status: BorrowingStatus
    
    model_config = ConfigDict(from_attributes=True)

class BorrowingReturn(BaseModel):
    # İade sırasında ek veri almak istenirse eklenebilir.
    pass

# --- Reservation ---
class ReservationCreate(BaseModel):
    book_id: uuid.UUID

class ReservationRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    book_id: uuid.UUID
    reservation_date: datetime
    expires_at: datetime | None = None
    remaining_seconds: int | None = None
    queue_position: int = 1
    people_ahead: int = 0
    can_borrow_now: bool = False
    queue_message: str = ""
    status: ReservationStatus

    model_config = ConfigDict(from_attributes=True)

