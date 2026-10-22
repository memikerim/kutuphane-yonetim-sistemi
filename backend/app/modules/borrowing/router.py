import uuid

from fastapi import APIRouter, HTTPException, status

from app.core.database import DbSession
from app.modules.auth.dependencies import CurrentUser
from app.modules.borrowing import service
from app.modules.borrowing.schemas import (
    BorrowingCreate,
    BorrowingRead,
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


@router.patch("/borrowings/{id}/return", response_model=BorrowingRead, summary="Kitabı iade et")
def return_book(id: uuid.UUID, db: DbSession, current_user: CurrentUser):
    """
    Ödünç alınan kitabı iade eder.
    Kayıt durumu RETURNED yapılır, iade tarihi atılır ve kitap stoku 1 artırılır.
    """
    return handle_service_error(service.return_borrowing, db, current_user, id)


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
    Giriş yapan kullanıcının tüm rezervasyonlarını rezervasyon tarihine göre (en yeni en üstte) sıralı döner.
    """
    return service.get_user_reservations(db, current_user)
