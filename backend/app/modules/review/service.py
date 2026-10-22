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
from app.modules.review.models import Review, ReviewReaction
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
    "mallar",
    "malsın",
    "malsin",
    "mallık",
    "mallik",
    "angut",
    "dangalak",
    "beyinsiz",
    "şerefsiz",
    "serefsiz",
    "ahlaksız",
    "ahlaksiz",
    "haysiyetsiz",
    "karaktersiz",
    "onursuz",
    "pislik",
    "rezil",
    "iğrenç",
    "igrenc",
    "lanet",
    "defol",
    "defolun",
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
    "sik",
    "siktir",
    "sikik",
    "hassiktir",
    "hasiktir",
    "amk",
    "aq",
    "mk",
    "amq",
    "oç",
    "oc",
    "orospu",
    "oruspu",
    "piç",
    "pic",
    "picler",
    "piclik",
    "yavşak",
    "yavsak",
    "göt",
    "got",
    "gotu",
    "gotun",
    "gotum",
    "gotlek",
    "gotveren",
    "gotten",
    "gotler",
    "bok",
    "boktan",
    "boku",
    "bokun",
    "boklar",
    "bokluk",
    "pezevenk",
    "kaltak",
    "kahpe",
    "fahişe",
    "fahise",
    "kevaşe",
    "kevase",
    "gavat",
    "dalyarak",
    "yarrak",
    "yarak",
    "amcık",
    "amcik",
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
    "fucking",
    "fucker",
    "shit",
    "bitch",
    "asshole",
    "bastard",
}

# Ek aldığında her durumda kötü söz/hakaret olan Türkçe kökler (yumuşamış halleri dahil)
BANNED_UNCONDITIONAL_STEMS = (
    "aptal",
    "salak",
    "salağ",
    "salag",
    "gerizekal",
    "embesil",
    "ahmak",
    "ahmağ",
    "ahmag",
    "angut",
    "dangalak",
    "dangalağ",
    "dangalag",
    "beyinsiz",
    "şerefsiz",
    "serefsiz",
    "ahlaksız",
    "ahlaksiz",
    "haysiyetsiz",
    "karaktersiz",
    "onursuz",
    "terbiyesiz",
    "edepsiz",
    "namussuz",
    "alçak",
    "alçağ",
    "alcak",
    "pislik",
    "pisliğ",
    "pislig",
    "rezil",
    "iğrenç",
    "igrenc",
    "gerzek",
    "manyak",
    "manyağ",
    "köpek",
    "köpeğ",
    "kopek",
    "eşek",
    "eşeğ",
    "öküz",
    "okuz",
    "siktir",
    "hassiktir",
    "hasiktir",
    "orospu",
    "oruspu",
    "pezevenk",
    "pezeveng",
    "yavşak",
    "yavşağ",
    "yavsak",
    "yavsag",
    "kaltak",
    "kaltağ",
    "kahpe",
    "fahişe",
    "fahise",
    "kevaşe",
    "kevase",
    "gavat",
    "dalyarak",
    "yarrak",
    "yarrağ",
    "yarrag",
    "yaraklar",
    "yarağım",
    "yarağın",
    "yarağı",
    "amcık",
    "amcığ",
    "amcik",
    "amcig",
    "amına",
    "amina",
    "amını",
    "amini",
    "ibne",
    "puşt",
    "pust",
    "götlek",
    "gotlek",
    "götveren",
    "gotveren",
    "küfür",
    "küfr",
    "kufur",
    "hakaret",
)

# Kökleri masum kelimelerle çakışabileceği için güvenli istisna (whitelist) ile kontrol edilen kökler:
# - "sik*" -> sikke, siklet, siklon, siklamen, siklus, siklik hariç tüm çekimleri ("siktiklerim", "sikeyim", "sikerler", "sikim" vb.) yasaklıdır.
# - "göt*" -> götür* (götürmek, götürü vb.) hariç tüm çekimleri ("götü", "götün", "götten", "götler" vb.) yasaklıdır.
# - "bok*" -> boks* (boks, boksör vb.) ve bokeh hariç tüm çekimleri ("boktan", "boku", "boklar" vb.) yasaklıdır.
# - "piç*" -> piçuta hariç tüm çekimleri ("piçler", "piçlik", "piçin" vb.) yasaklıdır.
SAFE_SIK_PREFIXES = ("sikke", "siklet", "sikl")
SAFE_GOT_PREFIXES = ("götür", "götur")
SAFE_BOK_PREFIXES = ("boks", "bokeh")
SAFE_PIC_PREFIXES = ("piçuta",)

BANNED_PHRASES = [
    "geri zekalı",
    "geri zekali",
    "ruh hastası",
    "ruh hastasi",
    "hayvan herif",
    "çöp kitap",
    "berbat ötesi",
    "berbat bir kitap",
    "beş para etmez",
    "bes para etmez",
    "amına koy",
    "amina koy",
    "amına kod",
    "amina kod",
    "ananı sik",
    "anani sik",
    "siktir git",
    "defol git",
    "bok gibi",
    "çöp gibi",
]


def _normalize_tr(text: str) -> str:
    return text.replace("İ", "i").replace("I", "ı").lower().strip()


def _collapse_repeats(word: str) -> str:
    """Ardışık tekrarlanan harfleri tek harfe indirir (örn. 'siiiiiktiklerim' -> 'siktiklerim')."""
    return re.sub(r"(.)\1+", r"\1", word)


def _deobfuscate(text: str) -> str:
    """Nokta/tire veya rakamlarla gizlenmiş kelimeleri çözer (örn. 's.i.k' -> 'sik', 's1kt1r' -> 'siktir')."""
    leet_map = str.maketrans({"1": "i", "0": "o", "3": "e", "4": "a", "5": "s", "@": "a", "$": "s"})
    cleaned = text.translate(leet_map)
    # Harfler arasına konulan nokta, yıldız veya tireleri kaldır (örn: s.i.k.t.i.r -> siktir)
    cleaned = re.sub(r"(?<=\w)[\.\*\-_]+(?=\w)", "", cleaned)
    return cleaned


def _check_single_token(token: str) -> bool:
    """Tek bir kelimenin (veya tekrarları/gizlemesi çözülmüş halinin) yasaklı olup olmadığını denetler."""
    if not token:
        return False

    if token in BANNED_EXACT_WORDS:
        return True

    for stem in BANNED_UNCONDITIONAL_STEMS:
        if token.startswith(stem):
            return True

    # "sik-" kökü ve tüm Türkçe çekimli/ekli halleri ("siktiklerim", "sikeyim", "sikerim", "sikim", "sikilmiş" vb.)
    if token.startswith("sik") and not token.startswith(SAFE_SIK_PREFIXES):
        return True

    # "göt-" kökü ve çekimli halleri ("götürmek" türevleri hariç)
    if token.startswith("göt") and not token.startswith(SAFE_GOT_PREFIXES):
        return True

    # "bok-" kökü ve çekimli halleri ("boks", "boksör" vb. hariç)
    if token.startswith("bok") and not token.startswith(SAFE_BOK_PREFIXES):
        return True

    # "piç-" kökü ve çekimli halleri
    if token.startswith("piç") and not token.startswith(SAFE_PIC_PREFIXES):
        return True

    return False


def find_inappropriate_expression(comment: str | None) -> str | None:
    """Yorum metninde kötü söz veya uygunsuz ifade varsa yakalanan ifadeyi döner."""
    if not comment or not comment.strip():
        return None

    normalized = _normalize_tr(comment)
    deobfuscated = _deobfuscate(normalized)

    for phrase in BANNED_PHRASES:
        if phrase in normalized or phrase in deobfuscated:
            return phrase

    # Hem normal metindeki kelimeleri hem de gizlemesi çözülmüş kelimeleri kontrol et
    raw_tokens = re.findall(r"\w+", normalized)
    deob_tokens = re.findall(r"\w+", deobfuscated)

    for token in raw_tokens + deob_tokens:
        if _check_single_token(token):
            return token
        collapsed = _collapse_repeats(token)
        if collapsed != token and _check_single_token(collapsed):
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


def react_to_review(db: Session, user: User, review_id: uuid.UUID, value: int) -> Review:
    """
    Diğer kullanıcıların yorumlarına Beğen / Faydalı (1: Thumbs Up) veya
    Beğenme / Katılmıyorum (-1: Thumbs Down) tepkisi bırakır.
    Aynı tepkiye tekrar tıklanırsa tepki geri çekilir (toggle).
    """
    if value not in (1, -1):
        raise BusinessRuleError("Geçersiz tepki değeri (1 veya -1 olmalıdır).")

    review = db.get(Review, review_id)
    if not review:
        raise NotFoundError("Tepki bırakılmak istenen yorum bulunamadı")

    if review.user_id == user.id:
        raise BusinessRuleError("Kendi yorumunuza beğeni/beğenmeme tepkisi bırakamazsınız.")

    existing = db.scalar(
        select(ReviewReaction).where(
            ReviewReaction.review_id == review.id,
            ReviewReaction.user_id == user.id,
        )
    )

    if existing:
        if existing.value == value:
            db.delete(existing)
            action = "removed"
        else:
            existing.value = value
            action = "updated"
    else:
        db.add(ReviewReaction(review_id=review.id, user_id=user.id, value=value))
        action = "added"

    db.commit()
    db.expire(review, ["reactions"])
    db.refresh(review)
    logger.info(
        "Yorum tepkisi güncellendi (%s) -> review_id: %s, user_id: %s, value: %s",
        action,
        review.id,
        user.id,
        value,
    )
    return review


