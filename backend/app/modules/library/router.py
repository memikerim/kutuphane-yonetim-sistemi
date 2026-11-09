import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.core.database import DbSession
from app.modules.auth.dependencies import CurrentUser
from app.modules.library import service
from app.modules.library.schemas import (
    LibraryCreate,
    LibraryCreateResponse,
    LibraryMembershipApplyRequest,
    LibraryMembershipRead,
    LibraryMembershipRoleUpdate,
    LibraryMembershipStatusUpdate,
    LibraryRead,
    LibrarySettingsUpdate,
    LibraryStatusUpdate,
)

router = APIRouter(tags=["Libraries (Multi-Tenant)"])


def _handle(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except service.NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except service.ForbiddenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except service.BusinessRuleError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get(
    "/libraries",
    response_model=list[LibraryRead],
    summary="Onaylı kütüphaneleri listele ve isme göre ara",
)
def list_libraries(
    db: DbSession,
    search: str | None = Query(None, description="Kütüphane adına göre arama"),
):
    return service.list_approved_libraries(db, search=search)


@router.get(
    "/libraries/my",
    response_model=list[LibraryMembershipRead],
    summary="Kullanıcının kütüphane üyeliklerini ve başvurularını listele",
)
def get_my_memberships(db: DbSession, current_user: CurrentUser):
    return service.get_user_memberships(db, current_user)


@router.get(
    "/libraries/my-requests",
    response_model=list[LibraryRead],
    summary="Kullanıcının oluşturduğu kütüphane kurulum taleplerini listele",
)
def get_my_library_requests(db: DbSession, current_user: CurrentUser):
    return service.get_user_created_library_requests(db, current_user)


@router.post(
    "/libraries",
    response_model=LibraryCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Yeni bir kütüphane oluşturma talebinde bulun (PENDING)",
)
def create_library_request(data: LibraryCreate, db: DbSession, current_user: CurrentUser):
    return _handle(service.create_library_request, db, current_user, data)


@router.post(
    "/libraries/apply",
    response_model=LibraryMembershipRead,
    status_code=status.HTTP_201_CREATED,
    summary="Kütüphane ismi veya ID'si ile kütüphaneye üyelik başvurusu yap (PENDING)",
)
def apply_to_library(data: LibraryMembershipApplyRequest, db: DbSession, current_user: CurrentUser):
    return _handle(service.apply_to_library, db, current_user, data)


@router.get(
    "/libraries/{library_id}",
    response_model=LibraryRead,
    summary="Kütüphane detay ve kural bilgilerini getir",
)
def get_library_detail(library_id: uuid.UUID, db: DbSession):
    return _handle(service.get_library_detail, db, library_id)


@router.put(
    "/libraries/{library_id}/settings",
    response_model=LibraryRead,
    summary="Kütüphane ve ceza/ödünç ayarlarını güncelle (LIBRARY_ADMIN / SYSTEM_ADMIN)",
)
def update_library_settings(
    library_id: uuid.UUID,
    data: LibrarySettingsUpdate,
    db: DbSession,
    current_user: CurrentUser,
):
    return _handle(service.update_library_settings, db, current_user, library_id, data)


@router.get(
    "/libraries/{library_id}/members",
    response_model=list[LibraryMembershipRead],
    summary="Kütüphane üyelerini ve katılma başvurularını listele (İzole LIBRARY_ADMIN)",
)
def list_library_members(
    library_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
    status_filter: str | None = Query(None, alias="status", description="PENDING, APPROVED, REJECTED, BANNED, ALL"),
):
    return _handle(service.list_library_members, db, current_user, library_id, status_filter)


@router.post(
    "/libraries/{library_id}/members/{membership_id}/status",
    response_model=LibraryMembershipRead,
    summary="Üyelik başvurusunu onayla/reddet veya üyeyi kütüphaneden banla/banını kaldır (LIBRARY_ADMIN)",
)
def update_membership_status(
    library_id: uuid.UUID,
    membership_id: uuid.UUID,
    data: LibraryMembershipStatusUpdate,
    db: DbSession,
    current_user: CurrentUser,
):
    return _handle(
        service.update_membership_status,
        db,
        current_user,
        library_id,
        membership_id,
        data,
    )


@router.post(
    "/libraries/{library_id}/members/{membership_id}/role",
    response_model=LibraryMembershipRead,
    summary="Onaylı üyeye kütüphane yöneticisi (LIBRARY_ADMIN) yetkisi ver veya geri al",
)
def update_membership_role(
    library_id: uuid.UUID,
    membership_id: uuid.UUID,
    data: LibraryMembershipRoleUpdate,
    db: DbSession,
    current_user: CurrentUser,
):
    return _handle(
        service.update_membership_role,
        db,
        current_user,
        library_id,
        membership_id,
        data,
    )


# --- SYSTEM_ADMIN Endpoints ---
@router.get(
    "/system-admin/libraries",
    response_model=list[LibraryRead],
    summary="Sistemdeki tüm kütüphaneleri ve bekleyen kurulum taleplerini listele (SYSTEM_ADMIN)",
)
def system_admin_list_libraries(
    db: DbSession,
    current_user: CurrentUser,
    status_filter: str | None = Query(None, alias="status", description="PENDING, APPROVED, REJECTED, ALL"),
):
    return _handle(service.list_all_libraries_for_system_admin, db, current_user, status_filter)


@router.post(
    "/system-admin/libraries/{library_id}/status",
    response_model=LibraryRead,
    summary="Kütüphane kurulum talebini onayla (APPROVED -> Kurucu LIBRARY_ADMIN olur) veya reddet (SYSTEM_ADMIN)",
)
def system_admin_update_library_status(
    library_id: uuid.UUID,
    data: LibraryStatusUpdate,
    db: DbSession,
    current_user: CurrentUser,
):
    return _handle(
        service.update_library_status_by_system_admin,
        db,
        current_user,
        library_id,
        data.status,
    )

