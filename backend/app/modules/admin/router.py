import uuid
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy import func, select

from app.core.database import DbSession
from app.core.logging_config import get_system_logs
from app.modules.admin import service as admin_service
from app.modules.admin.schemas import (
    AdminUserItem,
    BanUserRequest,
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
from app.modules.borrowing.schemas import (
    AdminApproveBorrowRequest,
    AdminApproveReturnRequest,
    AdminRejectBorrowRequest,
    BorrowingRead,
    StockMovementCreate,
    StockMovementRead,
    StockMovementSummaryResponse,
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


@router.post(
    "/borrowings/{id}/approve-borrow",
    response_model=BorrowingRead,
    summary="Bekleyen ödünç alma talebini onayla ve teslim et (yalnızca ADMIN)",
)
def approve_borrow(
    id: uuid.UUID,
    admin: AdminUser,
    db: DbSession,
    data: AdminApproveBorrowRequest | None = Body(default=None),
):
    try:
        return borrowing_service.admin_approve_borrow(
            db,
            admin,
            id,
            admin_notes=data.admin_notes if data else None,
            copy_code=data.copy_code if data else None,
        )
    except borrowing_service.NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except borrowing_service.BusinessRuleError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post(
    "/borrowings/{id}/reject-borrow",
    response_model=BorrowingRead,
    summary="Bekleyen ödünç alma talebini reddet ve stoğu geri yükle (yalnızca ADMIN)",
)
def reject_borrow(
    id: uuid.UUID,
    admin: AdminUser,
    db: DbSession,
    data: AdminRejectBorrowRequest | None = Body(default=None),
):
    try:
        return borrowing_service.admin_reject_borrow(
            db, admin, id, admin_notes=data.admin_notes if data else None
        )
    except borrowing_service.NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except borrowing_service.BusinessRuleError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post(
    "/borrowings/{id}/approve-return",
    response_model=BorrowingRead,
    summary="İade talebini fiziksel durum kontrolüyle (Sağlam/Hasarlı/Kayıp) onayla (yalnızca ADMIN)",
)
def approve_return(
    id: uuid.UUID,
    admin: AdminUser,
    db: DbSession,
    data: AdminApproveReturnRequest | None = Body(default=None),
):
    req_data = data or AdminApproveReturnRequest()
    try:
        return borrowing_service.admin_approve_return(db, admin, id, req_data)
    except borrowing_service.NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except borrowing_service.BusinessRuleError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get(
    "/stock-movements",
    response_model=StockMovementSummaryResponse,
    summary="Stok hareketlerini ve hasar/kayıp raporlarını listele (yalnızca ADMIN)",
)
def list_stock_movements(
    admin: AdminUser,
    db: DbSession,
    condition: str | None = Query(None, description="Filtre: ALL, GOOD, DAMAGED, LOST, RESTOCK"),
    book_id: uuid.UUID | None = Query(None, description="Belirli bir kitaba göre filtrele"),
    limit: int = Query(100, ge=1, le=500),
):
    return borrowing_service.get_stock_movements_summary(
        db, condition=condition, book_id=book_id, limit=limit
    )


@router.post(
    "/stock-movements",
    response_model=StockMovementRead,
    status_code=status.HTTP_201_CREATED,
    summary="Manuel stok hareketi veya hasar/kayıp raporu ekle (yalnızca ADMIN)",
)
def create_stock_movement(
    data: StockMovementCreate,
    admin: AdminUser,
    db: DbSession,
):
    try:
        return borrowing_service.create_manual_stock_movement(db, admin, data)
    except borrowing_service.NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except borrowing_service.BusinessRuleError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get(
    "/users",
    response_model=list[AdminUserItem],
    summary="Tüm kullanıcıları, borç ve ban durumlarıyla listele (yalnızca ADMIN)",
)
def list_users(admin: AdminUser, db: DbSession):
    return admin_service.list_users_for_admin(db)


@router.post(
    "/users/{user_id}/ban",
    response_model=AdminUserItem,
    summary="Kullanıcıyı banla ve ban sebebi/notu ekle (yalnızca ADMIN)",
)
def ban_user_endpoint(
    user_id: uuid.UUID,
    admin: AdminUser,
    db: DbSession,
    data: BanUserRequest | None = Body(default=None),
):
    req = data or BanUserRequest()
    try:
        return admin_service.ban_user(db, admin, user_id, req.ban_reason)
    except borrowing_service.NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except borrowing_service.BusinessRuleError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post(
    "/users/{user_id}/unban",
    response_model=AdminUserItem,
    summary="Kullanıcının banını (hesap kısıtlamasını) kaldır (yalnızca ADMIN)",
)
def unban_user_endpoint(
    user_id: uuid.UUID,
    admin: AdminUser,
    db: DbSession,
):
    try:
        return admin_service.unban_user(db, admin, user_id)
    except borrowing_service.NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.post(
    "/borrowings/{borrowing_id}/approve-payment",
    response_model=BorrowingRead,
    summary="Kullanıcının ceza/tazminat ödemesini onayla ve borcu kapat (yalnızca ADMIN)",
)
def approve_penalty_payment_endpoint(
    borrowing_id: uuid.UUID,
    admin: AdminUser,
    db: DbSession,
):
    try:
        return admin_service.approve_penalty_payment(db, admin, borrowing_id)
    except borrowing_service.NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e




