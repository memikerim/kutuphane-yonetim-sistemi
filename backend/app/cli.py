"""Yönetim ve Örnek Veri (Seed) Komutları.

Kullanım (proje kökünden):
    docker-compose exec backend python -m app.cli make-admin <email>
    docker-compose exec backend python -m app.cli revoke-admin <email>
    docker-compose exec backend python -m app.cli seed
"""

import argparse
import sys

from sqlalchemy import select

import app.models  # noqa: F401  - tüm mapper'ları kaydeder
from app.core.database import SessionLocal
from app.modules.auth.models import RoleName
from app.modules.auth.service import get_or_create_role, get_user_by_email
from app.modules.borrowing.models import Borrowing, Reservation
from app.modules.catalog.models import Author, Book, Category, Publisher


def _set_admin(email: str, grant: bool) -> int:
    with SessionLocal() as db:
        user = get_user_by_email(db, email)
        if user is None:
            print(f"HATA: '{email}' adresiyle kayıtlı kullanıcı bulunamadı.", file=sys.stderr)
            return 1

        admin_role = get_or_create_role(db, RoleName.ADMIN)
        has_admin = admin_role in user.roles

        if grant and not has_admin:
            user.roles.append(admin_role)
        elif not grant and has_admin:
            user.roles.remove(admin_role)
        db.commit()

        roles = ", ".join(sorted(r.name.value for r in user.roles))
        print(f"OK: {user.email} -> roller: [{roles}]")
        return 0


def _seed_catalog() -> int:
    """Veritabanındaki eksik/test kayıtlarını temizler ve gerçek kitap, yazar, kategori, yayınevi verilerini ekler."""
    with SessionLocal() as db:
        # 1. Geçici "Test Book / TestPub / TestCat / Test Author" kayıtlarını temizle
        test_books = db.scalars(select(Book).where(Book.title.like("Test Book%"))).all()
        for tb in test_books:
            db.query(Borrowing).filter(Borrowing.book_id == tb.id).delete()
            db.query(Reservation).filter(Reservation.book_id == tb.id).delete()
            db.delete(tb)

        for tp in db.scalars(select(Publisher).where(Publisher.name.like("TestPub%"))).all():
            db.delete(tp)
        for tc in db.scalars(select(Category).where(Category.name.like("TestCat%"))).all():
            db.delete(tc)
        for ta in db.scalars(select(Author).where(Author.last_name.like("Author_%"))).all():
            db.delete(ta)
        db.commit()

        # 2. Yayınevleri (Publishers)
        publishers_data = {
            "İş Bankası Kültür Yayınları": "İstiklal Cad. Meşelik Sok. No:2 Beyoğlu/İstanbul | info@iskultur.com.tr",
            "Can Yayınları": "Hayriye Cad. No:2 Galatasaray/İstanbul | iletisim@canyayinlari.com",
            "İletişim Yayınları": "Cumhuriyet Cad. No:36 دارülbedayi Beyoğlu/İstanbul | iletisim@iletisim.com.tr",
            "Yapı Kredi Yayınları": "İstiklal Cad. No:161 Beyoğlu/İstanbul | ykykultur@ykykultur.com.tr",
            "İthaki Yayınları": "Caferağa Mah. Neşet Ömer Sok. No:10 Kadıköy/İstanbul | info@ithaki.com.tr",
            "Kolektif Kitap": "Caferağa Mah. Moda Cad. Kadıköy/İstanbul | info@kolektifkitap.com",
        }
        publishers_map: dict[str, Publisher] = {}
        for name, contact in publishers_data.items():
            pub = db.scalar(select(Publisher).where(Publisher.name == name))
            if not pub:
                pub = Publisher(name=name, contact_info=contact)
                db.add(pub)
                db.flush()
            else:
                pub.contact_info = contact
            publishers_map[name] = pub

        # 3. Kategoriler (Categories)
        categories_names = [
            "Dünya Klasikleri",
            "Türk Edebiyatı",
            "Roman",
            "Bilim Kurgu & Distopya",
            "Fantastik",
            "Psikoloji & Felsefe",
            "Tarih & Toplum",
            "Yazılım & Teknoloji",
        ]
        categories_map: dict[str, Category] = {}
        for cname in categories_names:
            cat = db.scalar(select(Category).where(Category.name == cname))
            if not cat:
                cat = Category(name=cname)
                db.add(cat)
                db.flush()
            categories_map[cname] = cat

        # 4. Yazarlar (Authors)
        authors_data = [
            ("Fyodor", "Dostoyevski"),
            ("Sabahattin", "Ali"),
            ("George", "Orwell"),
            ("Ahmet Hamdi", "Tanpınar"),
            ("Stefan", "Zweig"),
            ("Yaşar", "Kemal"),
            ("Frank", "Herbert"),
            ("J.R.R.", "Tolkien"),
            ("Albert", "Camus"),
            ("Victor", "Hugo"),
            ("Yuval Noah", "Harari"),
            ("Oğuz", "Atay"),
        ]
        authors_map: dict[str, Author] = {}
        for fname, lname in authors_data:
            key = f"{fname} {lname}"
            author = db.scalar(
                select(Author).where(Author.first_name == fname, Author.last_name == lname)
            )
            if not author:
                author = Author(first_name=fname, last_name=lname)
                db.add(author)
                db.flush()
            authors_map[key] = author

        # 5. Gerçek Kitaplar (Books) - Tüm yayınevi, yazar ve kategori ilişkileri dolu!
        books_catalog = [
            {
                "title": "Suç ve Ceza",
                "isbn": "978-975-05-0001",
                "published_year": 1866,
                "stock_count": 5,
                "publisher": "İş Bankası Kültür Yayınları",
                "authors": ["Fyodor Dostoyevski"],
                "categories": ["Dünya Klasikleri", "Roman", "Psikoloji & Felsefe"],
            },
            {
                "title": "Kürk Mantolu Madonna",
                "isbn": "978-975-363-8029",
                "published_year": 1943,
                "stock_count": 7,
                "publisher": "Yapı Kredi Yayınları",
                "authors": ["Sabahattin Ali"],
                "categories": ["Türk Edebiyatı", "Roman"],
            },
            {
                "title": "1984",
                "isbn": "978-975-07-18533",
                "published_year": 1949,
                "stock_count": 4,
                "publisher": "Can Yayınları",
                "authors": ["George Orwell"],
                "categories": ["Dünya Klasikleri", "Bilim Kurgu & Distopya", "Roman"],
            },
            {
                "title": "Saatleri Ayarlama Enstitüsü",
                "isbn": "978-975-995-5762",
                "published_year": 1961,
                "stock_count": 3,
                "publisher": "İletişim Yayınları",
                "authors": ["Ahmet Hamdi Tanpınar"],
                "categories": ["Türk Edebiyatı", "Roman"],
            },
            {
                "title": "Tutunamayanlar",
                "isbn": "978-975-470-0114",
                "published_year": 1972,
                "stock_count": 0,  # Stok=0 testi ve Rezerve Et testi için!
                "publisher": "İletişim Yayınları",
                "authors": ["Oğuz Atay"],
                "categories": ["Türk Edebiyatı", "Roman"],
            },
            {
                "title": "Dune",
                "isbn": "978-605-375-4794",
                "published_year": 1965,
                "stock_count": 6,
                "publisher": "İthaki Yayınları",
                "authors": ["Frank Herbert"],
                "categories": ["Bilim Kurgu & Distopya", "Roman"],
            },
            {
                "title": "Satranç",
                "isbn": "978-605-360-6116",
                "published_year": 1942,
                "stock_count": 8,
                "publisher": "İş Bankası Kültür Yayınları",
                "authors": ["Stefan Zweig"],
                "categories": ["Dünya Klasikleri", "Psikoloji & Felsefe"],
            },
            {
                "title": "İnce Memed 1",
                "isbn": "978-975-08-07145",
                "published_year": 1955,
                "stock_count": 4,
                "publisher": "Yapı Kredi Yayınları",
                "authors": ["Yaşar Kemal"],
                "categories": ["Türk Edebiyatı", "Roman"],
            },
            {
                "title": "Yüzüklerin Efendisi: Yüzük Kardeşliği",
                "isbn": "978-975-342-5",
                "published_year": 1954,
                "stock_count": 0,  # Stok=0 ve Rezervasyon testi için!
                "publisher": "İthaki Yayınları",
                "authors": ["J.R.R. Tolkien"],
                "categories": ["Fantastik", "Roman"],
            },
            {
                "title": "Yabancı",
                "isbn": "978-975-07-26439",
                "published_year": 1942,
                "stock_count": 5,
                "publisher": "Can Yayınları",
                "authors": ["Albert Camus"],
                "categories": ["Dünya Klasikleri", "Psikoloji & Felsefe"],
            },
            {
                "title": "Sefiller",
                "isbn": "978-605-332-4744",
                "published_year": 1862,
                "stock_count": 3,
                "publisher": "İş Bankası Kültür Yayınları",
                "authors": ["Victor Hugo"],
                "categories": ["Dünya Klasikleri", "Roman", "Tarih & Toplum"],
            },
            {
                "title": "Hayvan Çiftliği",
                "isbn": "978-975-07-19387",
                "published_year": 1945,
                "stock_count": 6,
                "publisher": "Can Yayınları",
                "authors": ["George Orwell"],
                "categories": ["Dünya Klasikleri", "Bilim Kurgu & Distopya"],
            },
            {
                "title": "Sapiens: İnsan Türünün Kısa Bir Tarihi",
                "isbn": "978-605-09-24923",
                "published_year": 2011,
                "stock_count": 5,
                "publisher": "Kolektif Kitap",
                "authors": ["Yuval Noah Harari"],
                "categories": ["Tarih & Toplum", "Psikoloji & Felsefe"],
            },
            {
                "title": "Kuyucaklı Yusuf",
                "isbn": "978-975-08-00269",
                "published_year": 1937,
                "stock_count": 4,
                "publisher": "Yapı Kredi Yayınları",
                "authors": ["Sabahattin Ali"],
                "categories": ["Türk Edebiyatı", "Roman"],
            },
        ]

        added_or_updated = 0
        for item in books_catalog:
            existing_book = db.scalar(
                select(Book).where(
                    (Book.isbn == item["isbn"]) | (Book.title == item["title"])
                )
            )
            pub_obj = publishers_map[item["publisher"]]
            author_objs = [authors_map[a] for a in item["authors"]]
            cat_objs = [categories_map[c] for c in item["categories"]]

            if existing_book:
                existing_book.title = item["title"]
                existing_book.isbn = item["isbn"]
                existing_book.published_year = item["published_year"]
                existing_book.publisher_id = pub_obj.id
                existing_book.authors = author_objs
                existing_book.categories = cat_objs
                if existing_book.stock_count is None:
                    existing_book.stock_count = item["stock_count"]
            else:
                new_book = Book(
                    title=item["title"],
                    isbn=item["isbn"],
                    published_year=item["published_year"],
                    stock_count=item["stock_count"],
                    publisher_id=pub_obj.id,
                    authors=author_objs,
                    categories=cat_objs,
                )
                db.add(new_book)
            added_or_updated += 1

        db.commit()
        print(
            f"OK: {len(publishers_map)} yayınevi, {len(categories_map)} kategori, "
            f"{len(authors_map)} yazar ve {added_or_updated} gerçek kitap eksiksiz olarak veritabanına işlendi!"
        )
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("make-admin", "Kullanıcıya ADMIN rolü ver"),
        ("revoke-admin", "Kullanıcıdan ADMIN rolünü al"),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("email")

    sub.add_parser("seed", help="Gerçek kitap, yazar, kategori ve yayınevi verilerini yükle")

    args = parser.parse_args()
    if args.command == "seed":
        return _seed_catalog()
    return _set_admin(args.email, grant=args.command == "make-admin")


if __name__ == "__main__":
    raise SystemExit(main())
