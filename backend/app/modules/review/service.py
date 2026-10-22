import logging
import re
import uuid
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.auth.models import RoleName, User
from app.modules.borrowing.models import Borrowing
from app.modules.catalog.models import Book
from app.modules.review.models import Review
from app.modules.review.schemas import ReviewCreate

logger = logging.getLogger(__name__)

# Kötü söz, argo ve hakaret filtre listesi (Türkçe ve yaygın İngilizce ifadeler)
BANNED_EXACT_WORDS = {
    "aptal",
    "salak",
    "gerizekalı",
    "gerizekali",
    "embesil",
    "ahmak",
    "mal",
    "angut",
    "dangalak",
    "beyinsiz",
    "şerefsiz",
    "serefsiz",
    "ahlaksız",
    "ahlaksiz",
    "haysiyetsiz",
    "karaktersiz",
    "pislik",
    "rezil",
    "iğrenç",
    "igrenc",
    "lanet",
    "defol",
    "terbiyesiz",
    "edepsiz",
    "namussuz",
    "alçak",
    "alcak",
    "köpek",
    "kopek",
    "eşek",
    "esek",
    "öküz",
    "okuz",
    "gerzek",
    "manyak",
    "siktir",
    "sikik",
    "amk",
    "aq",
    "oç",
    "orospu",
    "piç",
    "pic",
    "yavşak",
    "yavsak",
    "göt",
    "got",
    "bok",
    "boktan",
    "pezevenk",
    "kaltak",
    "ibne",
    "puşt",
    "pust",
    "küfür",
    "kufur",
    "hakaret",
    "çöp",
    "cop",
    "idiot",
    "stupid",
    "moron",
    "fuck",
    "shit",
    "bitch",
    "asshole",
    "bastard",
}

BANNED_PHRASES = [
    "geri zekalı",
    "geri zekali",
    "ruh hastası",
    "ruh hastasi",
    "hayvan herif",
    "çöp kitap",
    "berbat ötesi",
    "berbat bir kitap",
]


def _normalize_tr(text: str) -> str:
    return text.replace("İ", "i").replace("I", "ı").lower().strip()


def find_inappropriate_expression(comment: str | None) -> str | None:
    """Yorum metninde kötü söz veya uygunsuz ifade varsa yakalanan ifadeyi döner."""
    if not comment or not comment.strip():
        return None

    normalized = _normalize_tr(comment)

    for phrase in BANNED_PHRASES:
        if phrase in normalized:
            return phrase

    tokens = re.findall(r"\w+", normalized)
    for token in tokens:
        if token in BANNED_EXACT_WORDS:
            return token
        # Ek almış yaygın hakaret kökleri kontrolü
        for stem in (
            "aptal",
            "salak",
            "gerizekalı",
            "gerizekali",
            "şerefsiz",
            "serefsiz",
            "ahlaksız",
            "terbiyesiz",
            "beyinsiz",
            "karaktersiz",
            "siktir",
            "orospu",
            "pezevenk",
            "küfür",
            "hakaret",
        ):
            if token.startswith(stem):
                return token

    return None


class BusinessRuleError(Exception):
    """Genel iş kuralı ihlali."""


class NotFoundError(Exception):
    """Kayıt bulunamadığında fırlatılır."""


class DuplicateReviewError(BusinessRuleError):
    """Bir kullanıcı aynı kitaba ikinci kez yorum yapmaya çalıştığında fırlatılır."""


class PermissionDeniedError(Exception):
    """Yetkisiz silme işleminde fırlatılır."""


def create_review(db: Session, user: User, data: ReviewCreate) -> Review:
    """Kitaba kullanıcı tarafından yeni bir değerlendirme/yorum ekler.

    İş Kuralları:
    - Kitap veritabanında mevcut olmalıdır.
    - Yorum metni kötü söz / hakaret filtresinden geçmelidir.
    - Kullanıcı kitabı daha önce ödünç almış olmalıdır (Borrowing kaydı bulunmalıdır).
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

    # Kural 1: Kötü söz / uygunsuz ifade filtresi
    bad_word = find_inappropriate_expression(data.comment)
    if bad_word is not None:
        logger.warning(
            "Yorum ekleme reddedildi (Uygunsuz ifade: '%s') -> user_id: %s, book_id: %s",
            bad_word,
            user.id,
            book.id,
        )
        raise BusinessRuleError(
            f"Yorumunuz eklenemedi: Yorumunuzda topluluk kurallarına aykırı/uygunsuz ifade ('{bad_word}') tespit edildi."
        )

    # Kural 2: Kullanıcı kitabı daha önce ödünç almış olmalı (aktif veya iade edilmiş)
    has_borrowed = db.scalar(
        select(Borrowing.id).where(
            Borrowing.user_id == user.id,
            Borrowing.book_id == book.id,
        )
    )
    if has_borrowed is None:
        logger.warning(
            "Yorum ekleme reddedildi: Kullanıcı kitabı daha önce ödünç almamış -> user_id: %s, book_id: %s",
            user.id,
            book.id,
        )
        raise BusinessRuleError(
            "Yorumunuz eklenemedi: Bu kitabı daha önce ödünç almadığınız için değerlendirme yapamazsınız."
        )


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


def delete_review(db: Session, user: User, review_id: uuid.UUID) -> None:
    """
    Yorumu siler.
    Kullanıcı kendi yorumunu silebilir; ADMIN rolündeki kullanıcılar ise tüm yorumları silebilir.
    """
    review = db.get(Review, review_id)
    if not review:
        raise NotFoundError("Silinmek istenen yorum bulunamadı")

    is_admin = any(
        (r.name == RoleName.ADMIN or str(r.name) == "ADMIN") for r in (user.roles or [])
    )
    if review.user_id != user.id and not is_admin:
        logger.warning(
            "Yetkisiz yorum silme denemesi engellendi -> review_id: %s, requester: %s, owner: %s",
            review_id,
            user.id,
            review.user_id,
        )
        raise PermissionDeniedError("Bu yorumu silme yetkiniz bulunmamaktadır.")

    db.delete(review)
    db.commit()
    logger.info(
        "Yorum başarıyla silindi -> review_id: %s, deleted_by: %s, is_admin: %s",
        review_id,
        user.id,
        is_admin,
    )

