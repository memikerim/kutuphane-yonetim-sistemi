from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.core.database import DbSession
from app.modules.admin.schemas import DashboardResponse, DashboardStats
from app.modules.auth.dependencies import require_roles
from app.modules.auth.models import RoleName, User
from app.modules.borrowing.models import (
    Borrowing,
    BorrowingStatus,
    Reservation,
    ReservationStatus,
)
from app.modules.catalog.models import Book

router = APIRouter(prefix="/admin", tags=["Admin"])

AdminUser = Annotated[User, Depends(require_roles([RoleName.ADMIN]))]


@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    summary="Yönetici paneli özeti (yalnızca ADMIN)",
    responses={
        401: {"description": "Token yok / geçersiz"},
        403: {"description": "ADMIN rolü gerekli"},
    },
)
def dashboard(admin: AdminUser, db: DbSession):
    def count(stmt) -> int:
        return db.scalar(stmt) or 0

    stats = DashboardStats(
        total_users=count(select(func.count()).select_from(User)),
        total_books=count(select(func.count()).select_from(Book)),
        active_borrowings=count(
            select(func.count())
            .select_from(Borrowing)
            .where(Borrowing.status == BorrowingStatus.ACTIVE)
        ),
        pending_reservations=count(
            select(func.count())
            .select_from(Reservation)
            .where(Reservation.status == ReservationStatus.PENDING)
        ),
    )
    return DashboardResponse(message=f"Hoş geldin, {admin.first_name}!", stats=stats)

