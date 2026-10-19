import logging
import uuid
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.auth.models import User
from app.modules.catalog.models import Book
from app.modules.review.models import Review
from app.modules.review.schemas import ReviewCreate

logger = logging.getLogger(__name__)


class BusinessRuleError(Exception):
    """Genel iş kuralı ihlali."""


class NotFoundError(Exception):
    """Kayıt bulunamadığında fırlatılır."""


class DuplicateReviewError(BusinessRuleError):
    """Bir kullanıcı aynı kitaba ikinci kez yorum yapmaya çalıştığında fırlatılır."""


def create_review(db: Session, user: User, data: ReviewCreate) -> Review:
    """Kitaba kullanıcı tarafından yeni bir değerlendirme/yorum ekler.
    
    İş Kuralları:
    - Kitap veritabanında mevcut olmalıdır.
    - Bir kullanıcı aynı kitaba birden fazla yorum yapamaz (uq_reviews_user_book kısıtlaması).
    """
    book = db.get(Book, data.book_id)
    if not book:
        logger.warning(
            "Yorum ekleme başarısız: Kitap bulunamadı. User ID: %s, Book ID: %s",
            user.id,
            data.book_id,
        )
        raise NotFoundError("Değerlendirme yapılmak istenen kitap bulunamadı")

    review = Review(
        user_id=user.id,
        book_id=book.id,
        rating=data.rating,
        comment=data.comment,
    )
    db.add(review)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        error_msg = str(exc.orig) if exc.orig else ""
        if "uq_reviews_user_book" in error_msg or "reviews.user_id" in error_msg:
            logger.warning(
                "Mükerrer yorum denemesi engellendi. User ID: %s, Book ID: %s",
                user.id,
                data.book_id,
            )
            raise DuplicateReviewError(
                "Bu kitaba daha önce yorum yaptınız. Her kitaba yalnızca bir kez değerlendirme yapılabilir."
            ) from exc
        
        logger.error(
            "Yorum eklenirken veritabanı kısıtlama hatası oluştu: %s",
            exc,
            exc_info=True,
        )
        raise BusinessRuleError("Yorum kaydedilemedi, kural ihlali oluştu.") from exc

    db.refresh(review)
    logger.info(
        "Yeni yorum eklendi: Review ID: %s, User ID: %s, Book ID: %s, Puan: %d",
        review.id,
        user.id,
        book.id,
        review.rating,
    )
    return review


def get_reviews(db: Session, book_id: uuid.UUID | None = None) -> Sequence[Review]:
    """Tüm yorumları veya belirli bir kitaba ait yorumları oluşturulma tarihine göre listeler."""
    stmt = select(Review).order_by(Review.created_at.desc())
    if book_id is not None:
        stmt = stmt.where(Review.book_id == book_id)
    return db.scalars(stmt).all()
