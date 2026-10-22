import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.core.database import DbSession
from app.modules.auth.dependencies import CurrentUser
from app.modules.review import service
from app.modules.review.schemas import ReviewCreate, ReviewRead

router = APIRouter(prefix="/reviews", tags=["Review & Rating"])


def handle_service_error(func, *args, **kwargs):
    """Domain hatalarını uygun HTTP durum kodlarına dönüştürür."""
    try:
        return func(*args, **kwargs)
    except service.NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except service.PermissionDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except service.DuplicateReviewError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except service.BusinessRuleError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post(
    "",
    response_model=ReviewRead,
    status_code=status.HTTP_201_CREATED,
    summary="Kitap için yeni değerlendirme/yorum yap",
    description=(
        "Giriş yapmış kullanıcı bir kitaba 1-5 arasında puan ve opsiyonel yorum bırakır. "
        "Aynı kullanıcı aynı kitaba yalnızca bir kez değerlendirme yapabilir. "
        "Mükerrer değerlendirmelerde 400 Bad Request döner."
    ),
    responses={
        201: {"description": "Yorum ve puan başarıyla kaydedildi."},
        400: {"description": "Aynı kitaba mükerrer yorum yapılması veya geçersiz veri."},
        401: {"description": "Yetkilendirme hatası (Giriş yapılmamış)."},
        404: {"description": "Değerlendirilmek istenen kitap bulunamadı."},
    },
)
def create_review(data: ReviewCreate, db: DbSession, current_user: CurrentUser):
    return handle_service_error(service.create_review, db, current_user, data)


@router.get(
    "",
    response_model=list[ReviewRead],
    summary="Kitap değerlendirmelerini ve yorumları listele",
    description=(
        "Herkese açık uç nokta. Tüm değerlendirmeleri ya da belirli bir kitaba (book_id) "
        "ait değerlendirmeleri en yeniden en eskiye doğru listeler."
    ),
    responses={
        200: {"description": "Değerlendirmeler başarıyla getirildi."},
    },
)
def get_reviews(
    db: DbSession,
    book_id: uuid.UUID | None = Query(
        None,
        description="Filtrelenecek kitabın kimliği (opsiyonel)",
    ),
):
    return service.get_reviews(db, book_id=book_id)


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Yorumu sil (Yorum sahibi veya ADMIN)",
    description=(
        "Kullanıcı kendi yaptığı değerlendirmeyi silebilir. "
        "ADMIN rolüne sahip yöneticiler ise herhangi bir kullanıcının yorumunu silebilir."
    ),
)
def delete_review(id: uuid.UUID, db: DbSession, current_user: CurrentUser):
    handle_service_error(service.delete_review, db, current_user, id)
    return None

