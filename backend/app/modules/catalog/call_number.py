import re
from typing import Any

# Dewey Onlu Sınıflama Sistemi (DDC) Anahtar Kelime Haritası
DEWEY_MAP: dict[str, str] = {
    # 800 - Edebiyat ve Retorik
    "roman": "823.91",
    "türk edebiyatı": "894.35",
    "dünya edebiyatı": "808.83",
    "klasik": "808.8",
    "distopya": "823.91",
    "bilim kurgu": "823.087",
    "fantastik": "823.087",
    "şiir": "894.31",
    "tiyatro": "894.32",
    "öykü": "894.33",
    "hikaye": "894.33",
    "deneme": "808.4",
    # 100 - Felsefe ve Psikoloji
    "felsefe": "100",
    "psikoloji": "150",
    "kişisel gelişim": "158.1",
    "düşünce": "190",
    "mantık": "160",
    "etik": "170",
    # 200 - Din ve Teoloji
    "din": "200",
    "ilahiyat": "297",
    "mitoloji": "292",
    # 300 - Toplum Bilimleri
    "sosyoloji": "301",
    "siyaset": "320",
    "politika": "320",
    "ekonomi": "330",
    "iktisat": "330",
    "hukuk": "340",
    "eğitim": "370",
    # 500 - Doğa Bilimleri ve Matematik
    "bilim": "500",
    "matematik": "510",
    "astronomi": "520",
    "fizik": "530",
    "kimya": "540",
    "biyoloji": "570",
    # 600 - Teknoloji ve Uygulamalı Bilimler
    "teknoloji": "600",
    "tıp": "610",
    "sağlık": "613",
    "mühendislik": "620",
    "yazılım": "005.1",
    "bilgisayar": "004",
    "işletme": "658",
    # 700 - Sanat ve Eğlence
    "sanat": "700",
    "mimarlık": "720",
    "resim": "750",
    "müzik": "780",
    "sinema": "791.43",
    # 900 - Tarih, Coğrafya ve Biyografi
    "tarih": "900",
    "türk tarihi": "956.1",
    "dünya tarihi": "909",
    "biyografi": "920",
    "otobiyografi": "920",
    "anı": "920",
    "coğrafya": "910",
}


def _clean_str(text: str) -> str:
    turkish_map = {
        "ç": "c", "Ç": "C",
        "ğ": "g", "Ğ": "G",
        "ı": "i", "I": "I", "İ": "I",
        "ö": "o", "Ö": "O",
        "ş": "s", "Ş": "S",
        "ü": "u", "Ü": "U",
        "â": "a", "Â": "A",
        "î": "i", "Î": "I",
        "û": "u", "Û": "U",
    }
    for tr, eng in turkish_map.items():
        text = text.replace(tr, eng)
    return text


def get_cutter_number(author_name: str | None, title: str | None) -> str:
    """Yazar soyadının ilk 3 harfini (Cutter-Sanborn standardı) üretir."""
    target = author_name.strip() if author_name and author_name.strip() else ""
    if not target and title:
        target = title.strip()
    if not target:
        return "GEN"

    words = target.split()
    # Genelde son kelime soyadıdır
    last_word = words[-1] if words else target
    cleaned = _clean_str(last_word).upper()
    letters_only = "".join(ch for ch in cleaned if ch.isalpha())
    if len(letters_only) >= 3:
        return letters_only[:3]
    return (letters_only + "XXX")[:3]


def generate_dewey_call_number(
    categories: list[Any] | None,
    author_name: str | None,
    title: str | None,
    published_year: int | None = None,
) -> str:
    """
    Kitap için kütüphane standartlarında Dewey Sınıflama Yer Kodu (Call Number) üretir.
    Örnek: '823.91 / ORW-1949' veya '894.35 / HIK'
    """
    dewey_code = "800"  # Varsayılan genel edebiyat / genel koleksiyon
    if categories:
        for cat in categories:
            cat_name = getattr(cat, "name", str(cat)).lower()
            for key, val in DEWEY_MAP.items():
                if key in cat_name:
                    dewey_code = val
                    break
            if dewey_code != "800":
                break

    cutter = get_cutter_number(author_name, title)
    if published_year and 1000 <= published_year <= 2100:
        return f"{dewey_code} / {cutter}-{published_year}"
    return f"{dewey_code} / {cutter}"


def get_clean_isbn(isbn: str | None) -> str:
    if not isbn:
        return "0000000000000"
    digits = "".join(ch for ch in isbn if ch.isdigit())
    return digits or "0000000000000"


def format_copy_code(isbn: str | None, copy_number: int) -> str:
    """Tekil nüsha / demirbaş kodunu üretir: örn. 'DEM-9789750718533-K1'"""
    clean_isbn = get_clean_isbn(isbn)
    return f"DEM-{clean_isbn}-K{copy_number}"


def format_barcode(isbn: str | None, copy_number: int) -> str:
    """Fiziki nüsha barkodunu üretir: örn. '978975071853301'"""
    clean_isbn = get_clean_isbn(isbn)
    return f"{clean_isbn}{copy_number:02d}"

