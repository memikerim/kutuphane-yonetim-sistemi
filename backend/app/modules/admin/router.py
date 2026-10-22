import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select

from app.core.database import DbSession
from app.core.logging_config import get_system_logs
from app.modules.admin import service as admin_service
from app.modules.admin.schemas import (
    DashboardResponse,
    DashboardStats,
    SystemLogEntry,
    UnpaidPenaltiesResponse,
)
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


@router.get(
    "/unpaid-penalties",
    response_model=UnpaidPenaltiesResponse,
    summary="Ödenmemiş borçları ve gecikme cezalarını listele (yalnızca ADMIN)",
    description=(
        "İade edilmiş ama cezası henüz ödenmemiş kayıtları ve şu an teslim tarihi geçmiş "
        "aktif (OVERDUE) ödünçlerden doğan güncel borçları kullanıcı ve kitap bilgileriyle listeler."
    ),
)
def list_unpaid_penalties(admin: AdminUser, db: DbSession):
    return admin_service.get_unpaid_penalties(db)


@router.get(
    "/logs",
    response_model=list[SystemLogEntry],
    summary="Sistem log geçmişini listele (yalnızca ADMIN)",
    description="Sistemde gerçekleşen son işlemleri kategori ve log seviyesi filtresiyle döndürür.",
)
def list_system_logs(
    admin: AdminUser,
    limit: int = Query(100, ge=1, le=200, description="Döndürülecek maksimum log sayısı"),
    category: str | None = Query(None, description="Kategori filtresi (AUTH, BORROWING, RESERVATION, PENALTY, REVIEW, CATALOG, SYSTEM)"),
    level: str | None = Query(None, description="Seviye filtresi (INFO, WARNING, ERROR)"),
):
    return get_system_logs(limit=limit, category=category, level=level)



