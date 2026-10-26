import uuid

from fastapi import APIRouter, Body, HTTPException, status

from app.core.database import DbSession
from app.modules.auth.dependencies import CurrentUser
from app.modules.borrowing import service
from app.modules.borrowing.schemas import (
    BorrowingCreate,
    BorrowingRead,
    BorrowingReturn,
    ReservationCreate,
    ReservationRead,
)

router = APIRouter(tags=["Borrowing & Reservations"])


def handle_service_error(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except service.NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except service.BusinessRuleError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


# --- Borrowing Endpoints ---
@router.get("/borrowings", response_model=list[BorrowingRead], summary="Ödünç aldığım kitapları listele")
def get_my_borrowings(db: DbSession, current_user: CurrentUser):
    """
    Giriş yapan kullanıcının ödünç aldığı tüm kitapları (aktif ve iade edilmiş) ödünç tarihine göre sıralı döner.
    """
    return service.get_user_borrowings(db, current_user)


@router.post("/borrowings", response_model=BorrowingRead, status_code=status.HTTP_201_CREATED, summary="Kitap ödünç al")
def borrow_book(data: BorrowingCreate, db: DbSession, current_user: CurrentUser):
    """
    Kitap ödünç alır. 
    İlgili kitabın stoku 1 azaltılır. Eğer stok 0 ise işlem reddedilir.
    """
    return handle_service_error(service.create_borrowing, db, current_user, data)


@router.patch("/borrowings/{id}/return", response_model=BorrowingRead, summary="Kitabı iade et veya iade talebi oluştur")
def return_book(
    id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
    data: BorrowingReturn | None = Body(default=None),
):
    """
    Ödünç alınan kitabı iade eder veya fiziksel kontrol için görevli onay kuyruğuna (PENDING_RETURN) gönderir.
    """
    return handle_service_error(service.return_borrowing, db, current_user, id, data)


@router.post("/borrowings/{id}/cancel-request", response_model=BorrowingRead, summary="Bekleyen ödünç talebini iptal et")
def cancel_borrow_request(id: uuid.UUID, db: DbSession, current_user: CurrentUser):
    """
    Henüz görevli tarafından onaylanmamış (PENDING_BORROW) ödünç talebini iptal eder ve ayrılan stoğu rafa geri ekler.
    """
    return handle_service_error(service.cancel_borrow_request, db, current_user, id)


@router.post("/borrowings/{id}/pay-penalty", response_model=BorrowingRead, summary="Gecikme cezasını öde")
def pay_penalty(id: uuid.UUID, db: DbSession, current_user: CurrentUser):
    """
    Kullanıcının ilgili ödünç işlemine ait gecikme cezasını ödediğini işaretler (is_penalty_paid = True).
    """
    return handle_service_error(service.pay_borrowing_penalty, db, current_user, id)



# --- Reservation Endpoints ---
@router.post("/reservations", response_model=ReservationRead, status_code=status.HTTP_201_CREATED, summary="Kitap rezervasyonu yap")
def create_reservation(data: ReservationCreate, db: DbSession, current_user: CurrentUser):
    """
    Kullanıcı bir kitap için rezervasyon yapar.
    Aynı kullanıcı aynı kitap için zaten PENDING durumunda bir rezervasyona sahipse reddedilir.
    """
    return handle_service_error(service.create_reservation, db, current_user, data)


@router.get("/reservations", response_model=list[ReservationRead], summary="Rezervasyonlarımı listele")
def get_my_reservations(db: DbSession, current_user: CurrentUser):
    """
    Giriş yapan kullanıcının aktif rezervasyonlarını sıra ve 24 saatlik kalan süre bilgisiyle döner.
    """
    return service.get_user_reservations(db, current_user)


@router.delete("/reservations/{id}", status_code=status.HTTP_204_NO_CONTENT, summary="Rezervasyonu iptal et / sil")
def cancel_reservation(id: uuid.UUID, db: DbSession, current_user: CurrentUser):
    """
    Giriş yapan kullanıcının bekleyen rezervasyonunu iptal ederek rezerve listesinden siler.
    """
    handle_service_error(service.cancel_reservation, db, current_user, id)
    return None

