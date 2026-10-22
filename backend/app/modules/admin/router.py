import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select

from app.core.database import DbSession
from app.modules.admin.schemas import DashboardResponse, DashboardStats
from app.modules.auth.dependencies import require_roles
from app.modules.auth.models import RoleName, User
from app.modules.borrowing import service as borrowing_service
from app.modules.borrowing.models import (
    Borrowing,
    BorrowingStatus,
    Reservation,
    ReservationStatus,
)
from app.modules.borrowing.schemas import BorrowingRead
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
            .where(Borrowing.status.in_([BorrowingStatus.ACTIVE, BorrowingStatus.OVERDUE]))
        ),
        pending_reservations=count(
            select(func.count())
            .select_from(Reservation)
            .where(Reservation.status == ReservationStatus.PENDING)
        ),
    )
    return DashboardResponse(message=f"Hoş geldin, {admin.first_name}!", stats=stats)


@router.get(
    "/borrowings",
    response_model=list[BorrowingRead],
    summary="Tüm ödünç işlemlerini listele (yalnızca ADMIN)",
)
def list_all_borrowings(admin: AdminUser, db: DbSession):
    """Sistemdeki tüm ödünç alma kayıtlarını listeler (Admin paneli için)."""
    return borrowing_service.get_all_borrowings(db)


@router.patch(
    "/borrowings/{id}/simulate-overdue",
    response_model=BorrowingRead,
    summary="Gecikme simüle et (-5 gün) (yalnızca ADMIN)",
)
def simulate_overdue(id: uuid.UUID, admin: AdminUser, db: DbSession):
    """
    Canlı sunum / test amacıyla seçilen ödünç kaydının due_date değerini 5 gün öncesine çeker
    ve durumunu OVERDUE yapar.
    """
    try:
        return borrowing_service.simulate_overdue_borrowing(db, id)
    except borrowing_service.NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except borrowing_service.BusinessRuleError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


