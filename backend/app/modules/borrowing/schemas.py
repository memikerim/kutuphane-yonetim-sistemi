import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.config import settings
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
    penalty_amount: float = 0.0
    is_penalty_paid: bool = False
    overdue_days: int = 0
    user_email: str | None = None
    user_full_name: str | None = None
    book_title: str | None = None

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def compute_dynamic_overdue(self) -> "BorrowingRead":
        today = date.today()
        if self.status != BorrowingStatus.RETURNED:
            if today > self.due_date:
                days = (today - self.due_date).days
                self.overdue_days = days
                self.penalty_amount = round(days * settings.DAILY_PENALTY_RATE, 2)
                self.status = BorrowingStatus.OVERDUE
            else:
                self.overdue_days = 0
        else:
            if self.return_date and self.return_date > self.due_date:
                self.overdue_days = (self.return_date - self.due_date).days
            elif self.penalty_amount > 0 and settings.DAILY_PENALTY_RATE > 0:
                self.overdue_days = int(round(self.penalty_amount / settings.DAILY_PENALTY_RATE))
        return self


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

