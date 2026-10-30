import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.config import settings
from app.modules.borrowing.models import BorrowingStatus, ReservationStatus

# --- Borrowing ---
class BorrowingCreate(BaseModel):
    book_id: uuid.UUID
    due_date: date = Field(description="İade edilmesi gereken son tarih")
    request_approval: bool = Field(
        default=False,
        description="True ise doğrudan aktifleşmek yerine görevli onay kuyruğuna (PENDING_BORROW) düşer",
    )
    notes: str | None = Field(default=None, max_length=500)


class BorrowingRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    book_id: uuid.UUID
    borrow_date: date
    due_date: date
    return_date: date | None = None
    status: BorrowingStatus
    approval_status: str = "APPROVED"
    return_condition: str = "GOOD"
    damage_penalty: float = 0.0
    return_notes: str | None = None
    admin_notes: str | None = None
    penalty_amount: float = 0.0
    is_penalty_paid: bool = False
    penalty_payment_status: str = "UNPAID"
    penalty_paid_at: datetime | None = None
    overdue_days: int = 0
    user_email: str | None = None
    user_full_name: str | None = None
    user_is_banned: bool = False
    user_ban_reason: str | None = None
    book_title: str | None = None
    book_isbn: str | None = None
    book_cover_url: str | None = None
    book_author: str | None = None
    copy_code: str | None = None
    call_number: str | None = None
    is_rejection_read: bool = False

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def compute_dynamic_overdue(self) -> "BorrowingRead":
        today = date.today()
        if self.status != BorrowingStatus.RETURNED:
            if self.approval_status == "PENDING_BORROW":
                self.overdue_days = 0
            elif today > self.due_date:
                days = (today - self.due_date).days
                self.overdue_days = days
                self.penalty_amount = round(
                    days * settings.DAILY_PENALTY_RATE + float(self.damage_penalty or 0.0), 2
                )
                self.status = BorrowingStatus.OVERDUE
            else:
                self.overdue_days = 0
        else:
            if self.return_date and self.return_date > self.due_date:
                self.overdue_days = (self.return_date - self.due_date).days
            else:
                overdue_part = max(
                    0.0, float(self.penalty_amount or 0.0) - float(self.damage_penalty or 0.0)
                )
                if overdue_part > 0 and settings.DAILY_PENALTY_RATE > 0:
                    self.overdue_days = int(round(overdue_part / settings.DAILY_PENALTY_RATE))
        return self


class BorrowingReturn(BaseModel):
    request_approval: bool = Field(
        default=False,
        description="True ise doğrudan iade edilmek yerine görevli kontrol ve onay kuyruğuna (PENDING_RETURN) düşer",
    )
    return_condition: str = Field(
        default="GOOD",
        description="Kitabın fiziksel durumu: GOOD (Sağlam), DAMAGED (Hasarlı), LOST (Kayıp)",
    )
    return_notes: str | None = Field(default=None, max_length=500)


class AdminApproveBorrowRequest(BaseModel):
    copy_code: str | None = Field(default=None, max_length=50, description="Teslim edilen nüshanın demirbaş kodu (örn: DEM-9789750718533-K1)")
    admin_notes: str | None = Field(default=None, max_length=500)


class AdminRejectBorrowRequest(BaseModel):
    admin_notes: str | None = Field(default=None, max_length=500)


class AdminApproveReturnRequest(BaseModel):
    verified_copy_code: str | None = Field(default=None, max_length=50, description="Teslim alınan ve fiziksel kontrolü yapılan nüsha kodu")
    return_condition: str = Field(
        default="GOOD",
        description="Görevli tarafından doğrulanan fiziksel durum: GOOD, DAMAGED, LOST",
    )
    damage_penalty: float | None = Field(
        default=None,
        ge=0,
        description="Hasar/kayıp kaynaklı ek tazminat tutarı (boş bırakılırsa varsayılan tarife uygulanır)",
    )
    withdraw_from_stock: bool | None = Field(
        default=None,
        description="True ise kitap ağır hasar/kayıp nedeniyle rafa geri eklenmez (stok artırılmaz)",
    )
    admin_notes: str | None = Field(default=None, max_length=500)


# --- Stock Movements & Damage/Loss Reports ---
class StockMovementCreate(BaseModel):
    book_id: uuid.UUID
    movement_type: str = Field(
        description="ADMIN_DAMAGE (Hasar Tespiti - Stoktan Düş), ADMIN_LOST (Kayıp Tespiti - Stoktan Düş), ADMIN_RESTOCK (Stok Girişi)"
    )
    quantity: int = Field(default=1, ge=1, le=500)
    notes: str | None = Field(default=None, max_length=500)


class StockMovementRead(BaseModel):
    id: uuid.UUID
    book_id: uuid.UUID
    book_title: str | None = None
    book_isbn: str | None = None
    user_id: uuid.UUID | None = None
    user_full_name: str | None = None
    user_email: str | None = None
    admin_id: uuid.UUID | None = None
    admin_full_name: str | None = None
    borrowing_id: uuid.UUID | None = None
    movement_type: str
    condition: str
    quantity_change: int
    stock_before: int
    stock_after: int
    penalty_added: float = 0.0
    notes: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StockMovementSummaryResponse(BaseModel):
    total_movements: int
    damaged_reports_count: int
    lost_reports_count: int
    damaged_count: int = 0
    lost_count: int = 0
    restock_count: int
    total_compensation_amount: float
    total_damage_lost_penalty: float = 0.0
    items: list[StockMovementRead]


class BookReadingRecord(BaseModel):
    borrowing_id: uuid.UUID
    user_id: uuid.UUID
    reader_name: str
    reader_email: str | None = None
    borrow_date: date
    due_date: date
    return_date: date | None = None
    status: str
    approval_status: str
    return_condition: str
    overdue_days: int = 0
    penalty_amount: float = 0.0
    damage_penalty: float = 0.0
    return_notes: str | None = None
    admin_notes: str | None = None


class BookHistoryStats(BaseModel):
    total_borrow_count: int = 0
    active_borrow_count: int = 0
    pending_approval_count: int = 0
    returned_count: int = 0
    damaged_count: int = 0
    lost_count: int = 0
    total_damage_loss_penalty: float = 0.0


class BookHistoryResponse(BaseModel):
    book_id: uuid.UUID
    book_title: str
    book_isbn: str
    current_stock: int
    stats: BookHistoryStats
    reading_history: list[BookReadingRecord]
    stock_movements: list[StockMovementRead]

# --- Reservation ---
class ReservationCreate(BaseModel):
    book_id: uuid.UUID

class ReservationRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    book_id: uuid.UUID
    reservation_date: datetime
    expires_at: datetime | None = None
    turn_starts_at: datetime | None = None
    remaining_seconds: int | None = None
    queue_position: int = 1
    people_ahead: int = 0
    can_borrow_now: bool = False
    queue_message: str = ""
    status: ReservationStatus

    model_config = ConfigDict(from_attributes=True)


# --- Notifications & Action Center ---
class NotificationItem(BaseModel):
    id: str
    target: str  # "USER" | "ADMIN"
    type: str  # RESERVATION_READY, PENALTY_DUE, PAYMENT_PENDING_APPROVAL, OVERDUE_BOOK, PENDING_BORROW, PENDING_RETURN, BANNED, ADMIN_PENDING_PAYMENT, ADMIN_PENDING_RETURN, ADMIN_PENDING_BORROW, ADMIN_OVERDUE
    severity: str  # "info" | "warning" | "error" | "success"
    title: str
    message: str
    meta: dict[str, Any] = Field(default_factory=dict)
    action_type: str | None = None
    created_at: datetime | None = None


class NotificationSummaryResponse(BaseModel):
    total_count: int = 0
    user_action_count: int = 0
    admin_action_count: int = 0
    pending_penalty_approvals: int = 0
    pending_return_approvals: int = 0
    pending_borrow_approvals: int = 0
    items: list[NotificationItem] = Field(default_factory=list)


