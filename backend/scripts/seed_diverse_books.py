import random
import sys
import uuid
from pathlib import Path

# Backend dizinini sys.path'e ekle
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.main  # Modellerin mapper'larını doğru yüklemesi için
from app.core.database import SessionLocal
from app.modules.catalog.models import Author, Book, Category, Publisher


BOOKS_DATA = [
    # --- YAZILIM, PROGRAMLAMA & TEKNOLOJİ ---
    {
        "title": "Clean Code: A Handbook of Agile Software Craftsmanship",
        "authors": [("Robert C.", "Martin")],
        "publisher": "Pearson Education",
        "isbn": "978-0-13-235088-4",
        "published_year": 2008,
        "categories": ["Yazılım & Teknoloji"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780132350884-L.jpg",
    },
    {
        "title": "The Pragmatic Programmer: Your Journey to Mastery",
        "authors": [("Andrew", "Hunt"), ("David", "Thomas")],
        "publisher": "Addison-Wesley",
        "isbn": "978-0-20-161622-4",
        "published_year": 1999,
        "categories": ["Yazılım & Teknoloji"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780201616224-L.jpg",
    },
    {
        "title": "Design Patterns: Elements of Reusable Object-Oriented Software",
        "authors": [("Erich", "Gamma"), ("Richard", "Helm"), ("Ralph", "Johnson"), ("John", "Vlissides")],
        "publisher": "Addison-Wesley",
        "isbn": "978-0-20-163361-0",
        "published_year": 1994,
        "categories": ["Yazılım & Teknoloji"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780201633610-L.jpg",
    },
    {
        "title": "Introduction to Algorithms",
        "authors": [("Thomas H.", "Cormen"), ("Charles E.", "Leiserson"), ("Ronald L.", "Rivest"), ("Clifford", "Stein")],
        "publisher": "MIT Press",
        "isbn": "978-0-26-203384-8",
        "published_year": 2009,
        "categories": ["Yazılım & Teknoloji"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780262033848-L.jpg",
    },
    {
        "title": "Refactoring: Improving the Design of Existing Code",
        "authors": [("Martin", "Fowler")],
        "publisher": "Addison-Wesley",
        "isbn": "978-0-13-475759-9",
        "published_year": 2018,
        "categories": ["Yazılım & Teknoloji"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780134757599-L.jpg",
    },
    {
        "title": "JavaScript: The Good Parts",
        "authors": [("Douglas", "Crockford")],
        "publisher": "O'Reilly Media",
        "isbn": "978-0-59-651774-8",
        "published_year": 2008,
        "categories": ["Yazılım & Teknoloji"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780596517748-L.jpg",
    },
    {
        "title": "The Mythical Man-Month: Essays on Software Engineering",
        "authors": [("Frederick P.", "Brooks")],
        "publisher": "Addison-Wesley",
        "isbn": "978-0-20-183595-3",
        "published_year": 1995,
        "categories": ["Yazılım & Teknoloji"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780201835953-L.jpg",
    },
    {
        "title": "Deep Learning with Python",
        "authors": [("François", "Chollet")],
        "publisher": "Manning Publications",
        "isbn": "978-1-61-729443-3",
        "published_year": 2017,
        "categories": ["Yazılım & Teknoloji"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9781617294433-L.jpg",
    },

    # --- KİŞİSEL GELİŞİM ---
    {
        "title": "Atomik Alışkanlıklar",
        "authors": [("James", "Clear")],
        "publisher": "Pegasus Yayınları",
        "isbn": "978-605-299-838-0",
        "published_year": 2018,
        "categories": ["Kişisel Gelişim", "Psikoloji & Felsefe"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9786052998380-L.jpg",
    },
    {
        "title": "Etkili İnsanların 7 Alışkanlığı",
        "authors": [("Stephen R.", "Covey")],
        "publisher": "Varlık Yayınları",
        "isbn": "978-975-434-195-9",
        "published_year": 1989,
        "categories": ["Kişisel Gelişim"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780743269513-L.jpg",
    },
    {
        "title": "Düşün ve Zengin Ol",
        "authors": [("Napoleon", "Hill")],
        "publisher": "Altın Kitaplar",
        "isbn": "978-975-21-0348-1",
        "published_year": 1937,
        "categories": ["Kişisel Gelişim"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9781585424337-L.jpg",
    },
    {
        "title": "İnsanın Anlam Arayışı",
        "authors": [("Viktor E.", "Frankl")],
        "publisher": "Okuyan Us Yayınevi",
        "isbn": "978-605-405-423-7",
        "published_year": 1946,
        "categories": ["Kişisel Gelişim", "Psikoloji & Felsefe"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780807014295-L.jpg",
    },
    {
        "title": "Bilinçaltının Gücü",
        "authors": [("Joseph", "Murphy")],
        "publisher": "Koridor Yayıncılık",
        "isbn": "978-605-418-802-4",
        "published_year": 1963,
        "categories": ["Kişisel Gelişim", "Psikoloji & Felsefe"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780735204553-L.jpg",
    },
    {
        "title": "Pürdikkat: Odaklanma Becerisini Nasıl Yitirdik?",
        "authors": [("Cal", "Newport")],
        "publisher": "Metropolis Kitap",
        "isbn": "978-605-671-192-3",
        "published_year": 2017,
        "categories": ["Kişisel Gelişim", "Yazılım & Teknoloji"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9781455586691-L.jpg",
    },

    # --- BİYOGRAFİ & OTOBİYOGRAFİ ---
    {
        "title": "Steve Jobs",
        "authors": [("Walter", "Isaacson")],
        "publisher": "Domingo Yayınevi",
        "isbn": "978-605-615-555-0",
        "published_year": 2011,
        "categories": ["Biyografi & Otobiyografi", "Yazılım & Teknoloji"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9781451648539-L.jpg",
    },
    {
        "title": "Elon Musk: Tesla, SpaceX ve Muhteşem Geleceğin Peşinde",
        "authors": [("Ashlee", "Vance")],
        "publisher": "Kronik Kitap",
        "isbn": "978-605-998-064-7",
        "published_year": 2015,
        "categories": ["Biyografi & Otobiyografi", "Yazılım & Teknoloji"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780062301239-L.jpg",
    },
    {
        "title": "Bir Bilim Adamının Romanı",
        "authors": [("Oğuz", "Atay")],
        "publisher": "İletişim Yayınları",
        "isbn": "978-975-47-0007-7",
        "published_year": 1975,
        "categories": ["Biyografi & Otobiyografi", "Türk Edebiyatı"],
        "cover_url": "https://covers.openlibrary.org/b/id/11149794-L.jpg",
    },
    {
        "title": "Leonardo da Vinci",
        "authors": [("Walter", "Isaacson")],
        "publisher": "Domingo Yayınevi",
        "isbn": "978-605-19-8038-6",
        "published_year": 2017,
        "categories": ["Biyografi & Otobiyografi", "Tarih & Toplum"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9781501139154-L.jpg",
    },
    {
        "title": "Akıl Oyunları",
        "authors": [("Sylvia", "Nasar")],
        "publisher": "Altın Kitaplar",
        "isbn": "978-975-21-0214-9",
        "published_year": 1998,
        "categories": ["Biyografi & Otobiyografi"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780684819068-L.jpg",
    },
    {
        "title": "Kendi Hayatının Şiirini Yazanlar",
        "authors": [("Stefan", "Zweig")],
        "publisher": "Türkiye İş Bankası Kültür Yayınları",
        "isbn": "978-605-33-2506-2",
        "published_year": 1928,
        "categories": ["Biyografi & Otobiyografi", "Dünya Klasikleri"],
        "cover_url": "https://covers.openlibrary.org/b/id/8231990-L.jpg",
    },

    # --- TÜRKÇE EDEBİYAT & ROMAN ---
    {
        "title": "Puslu Kıtalar Atlası",
        "authors": [("İhsan Oktay", "Anar")],
        "publisher": "İletişim Yayınları",
        "isbn": "978-975-47-0472-3",
        "published_year": 1995,
        "categories": ["Türk Edebiyatı", "Roman", "Fantastik"],
        "cover_url": "https://covers.openlibrary.org/b/id/12832960-L.jpg",
    },
    {
        "title": "Beyaz Kale",
        "authors": [("Orhan", "Pamuk")],
        "publisher": "İletişim Yayınları",
        "isbn": "978-975-47-0455-6",
        "published_year": 1985,
        "categories": ["Türk Edebiyatı", "Roman", "Tarih & Toplum"],
        "cover_url": "https://covers.openlibrary.org/b/id/10543306-L.jpg",
    },
    {
        "title": "Aylak Adam",
        "authors": [("Yusuf", "Atılgan")],
        "publisher": "Yapı Kredi Yayınları",
        "isbn": "978-975-08-1335-1",
        "published_year": 1959,
        "categories": ["Türk Edebiyatı", "Roman", "Psikoloji & Felsefe"],
        "cover_url": "https://covers.openlibrary.org/b/id/12308941-L.jpg",
    },
    {
        "title": "Huzur",
        "authors": [("Ahmet Hamdi", "Tanpınar")],
        "publisher": "Dergâh Yayınları",
        "isbn": "978-975-99-5577-9",
        "published_year": 1949,
        "categories": ["Türk Edebiyatı", "Roman"],
        "cover_url": "https://covers.openlibrary.org/b/id/12354821-L.jpg",
    },
    {
        "title": "Memleketimden İnsan Manzaraları",
        "authors": [("Nâzım", "Hikmet")],
        "publisher": "Yapı Kredi Yayınları",
        "isbn": "978-975-08-0447-2",
        "published_year": 2002,
        "categories": ["Türk Edebiyatı"],
        "cover_url": "https://covers.openlibrary.org/b/id/10217552-L.jpg",
    },

    # --- DÜNYA KLASİKLERİ & BİLİM KURGU ---
    {
        "title": "Dönüşüm",
        "authors": [("Franz", "Kafka")],
        "publisher": "Türkiye İş Bankası Kültür Yayınları",
        "isbn": "978-605-36-0930-8",
        "published_year": 1915,
        "categories": ["Dünya Klasikleri", "Roman", "Psikoloji & Felsefe"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780143105244-L.jpg",
    },
    {
        "title": "Fahrenheit 451",
        "authors": [("Ray", "Bradbury")],
        "publisher": "İthaki Yayınları",
        "isbn": "978-605-37-5781-8",
        "published_year": 1953,
        "categories": ["Bilim Kurgu & Distopya", "Dünya Klasikleri"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9786053757818-L.jpg",
    },
    {
        "title": "Yüzyıllık Yalnızlık",
        "authors": [("Gabriel García", "Márquez")],
        "publisher": "Can Yayınları",
        "isbn": "978-975-07-1936-3",
        "published_year": 1967,
        "categories": ["Dünya Klasikleri", "Roman"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9789750719363-L.jpg",
    },
    {
        "title": "Cesur Yeni Dünya",
        "authors": [("Aldous", "Huxley")],
        "publisher": "İthaki Yayınları",
        "isbn": "978-975-69-0216-5",
        "published_year": 1932,
        "categories": ["Bilim Kurgu & Distopya", "Dünya Klasikleri"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780060850524-L.jpg",
    },
    {
        "title": "Karamazov Kardeşler",
        "authors": [("Fyodor", "Dostoyevski")],
        "publisher": "Türkiye İş Bankası Kültür Yayınları",
        "isbn": "978-605-36-0987-2",
        "published_year": 1880,
        "categories": ["Dünya Klasikleri", "Roman", "Psikoloji & Felsefe"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780374528379-L.jpg",
    },
    {
        "title": "Bülbülü Öldürmek",
        "authors": [("Harper", "Lee")],
        "publisher": "Sel Yayıncılık",
        "isbn": "978-975-57-0701-3",
        "published_year": 1960,
        "categories": ["Dünya Klasikleri", "Roman"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780060935467-L.jpg",
    },
    {
        "title": "Otostopçunun Galaksi Rehberi",
        "authors": [("Douglas", "Adams")],
        "publisher": "Sarmal Yayınevi",
        "isbn": "978-975-73-8096-2",
        "published_year": 1979,
        "categories": ["Bilim Kurgu & Distopya"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780345391803-L.jpg",
    },
    {
        "title": "Körlük",
        "authors": [("José", "Saramago")],
        "publisher": "Kırmızı Kedi Yayınevi",
        "isbn": "978-605-29-8135-1",
        "published_year": 1995,
        "categories": ["Dünya Klasikleri", "Roman", "Psikoloji & Felsefe"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780156007757-L.jpg",
    },
]


def seed_books():
    db = SessionLocal()
    added_count = 0
    skipped_count = 0

    print("=== Kitap Veritabanı Zenginleştirme Başlatılıyor ===")

    try:
        for item in BOOKS_DATA:
            # 1. Kitap zaten var mı kontrol et (ISBN veya Başlık ile)
            clean_isbn = item["isbn"].replace("-", "").strip()
            existing = (
                db.query(Book)
                .filter(
                    (Book.isbn == item["isbn"])
                    | (Book.isbn == clean_isbn)
                    | (Book.title == item["title"])
                )
                .first()
            )
            if existing:
                print(f"[ATLANDI] Zaten mevcut: {item['title']} (ISBN: {existing.isbn})")
                skipped_count += 1
                continue

            # 2. Yayınevi bul veya oluştur
            pub_name = item["publisher"]
            pub = db.query(Publisher).filter(Publisher.name.ilike(pub_name)).first()
            if not pub:
                pub = Publisher(name=pub_name)
                db.add(pub)
                db.flush()

            # 3. Yazarları bul veya oluştur
            authors_list = []
            for first_name, last_name in item["authors"]:
                author = (
                    db.query(Author)
                    .filter(
                        Author.first_name.ilike(first_name),
                        Author.last_name.ilike(last_name),
                    )
                    .first()
                )
                if not author:
                    author = Author(first_name=first_name, last_name=last_name)
                    db.add(author)
                    db.flush()
                authors_list.append(author)

            # 4. Kategorileri bul veya oluştur
            categories_list = []
            for cat_name in item["categories"]:
                cat = db.query(Category).filter(Category.name.ilike(cat_name)).first()
                if not cat:
                    cat = Category(name=cat_name)
                    db.add(cat)
                    db.flush()
                categories_list.append(cat)

            # 5. Rastgele stok belirle (1 ile 10 arasında, çoğu 3-7)
            # Ağırlıklı rastgelelik: nadiren 0 veya 1 (rezervasyon denemeleri için), genelde 2-8
            stock = random.choice([0, 1, 2, 3, 3, 4, 4, 5, 5, 6, 7, 8, 9, 10])

            # 6. Yeni Kitabı oluştur
            new_book = Book(
                title=item["title"],
                isbn=item["isbn"],
                published_year=item["published_year"],
                stock_count=stock,
                cover_url=item["cover_url"],
                publisher=pub,
                authors=authors_list,
                categories=categories_list,
            )
            db.add(new_book)
            db.commit()
            added_count += 1
            print(
                f"[EKLENDİ] {new_book.title} | Stok: {stock} | Yazar: {', '.join(a.first_name + ' ' + a.last_name for a in authors_list)} | Yayınevi: {pub.name}"
            )

        print("\n=== Özet ===")
        print(f"Toplam Eklenen Yeni Kitap: {added_count}")
        print(f"Atlanan (Mevcut) Kitap: {skipped_count}")
        total_books = db.query(Book).count()
        print(f"Veritabanındaki Güncel Toplam Kitap Sayısı: {total_books}")

    except Exception as e:
        db.rollback()
        print(f"Hata oluştu: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_books()

