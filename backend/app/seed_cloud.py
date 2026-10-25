import json
import logging
from pathlib import Path
import uuid

import app.models  # Tüm modelleri Base.metadata'ya kaydeder
from app.core.base_model import Base
from app.core.database import SessionLocal, engine
from app.modules.auth.models import Role, RoleName, User
from app.modules.catalog.models import Author, Book, Category, Publisher

logger = logging.getLogger("app.seed_cloud")


def seed_cloud():
    """
    Bulut veritabanı (Neon.tech vb.) veya yeni kurulumlarda tabloları otomatik oluşturup
    initial_data.json dosyasındaki verileri idempotent (tekrarsız) olarak yükler.
    """
    # 0. Veritabanı tablolarının varlığını garanti et
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        logger.warning(f"[SEED] Tablo oluşturma sırasında uyarı/hata: {e}")

    json_path = Path(__file__).resolve().parent / "initial_data.json"
    if not json_path.exists():
        print(f"[SEED] initial_data.json dosyası bulunamadı: {json_path}")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    db = SessionLocal()
    try:
        # 1. Roller (USER, ADMIN)
        role_map = {}
        for r_name in [RoleName.USER, RoleName.ADMIN]:
            role = db.query(Role).filter(Role.name == r_name).first()
            if not role:
                role = Role(name=r_name)
                db.add(role)
                db.flush()
            role_map[r_name.value] = role
        db.commit()

        # 2. Kullanıcılar (Özellikle Memik Erim ADMIN)
        users_added = 0
        for u_data in data.get("users", []):
            user = db.query(User).filter(User.email == u_data["email"]).first()
            if not user:
                user_roles = [role_map[r] for r in u_data.get("roles", []) if r in role_map]
                user = User(
                    id=uuid.UUID(u_data["id"]) if "id" in u_data else uuid.uuid4(),
                    email=u_data["email"],
                    first_name=u_data["first_name"],
                    last_name=u_data["last_name"],
                    password_hash=u_data["password_hash"],
                    roles=user_roles,
                )
                db.add(user)
                users_added += 1
        db.commit()
        if users_added > 0:
            print(f"[SEED] {users_added} kullanıcı oluşturuldu.")

        # 3. Kitap kontrolü: Eğer veritabanında zaten kitap varsa katalog eklemesini atla (idempotent)
        book_count = db.query(Book).count()
        if book_count > 0:
            print(f"[SEED] Veritabanında zaten {book_count} kitap mevcut. Katalog seed atlanıyor.")
            return

        print("[SEED] Yeni veritabanı tespit edildi. initial_data.json verileri yükleniyor...")

        # 4. Yayınevleri
        publisher_map = {}
        for p_data in data.get("publishers", []):
            p_id = uuid.UUID(p_data["id"])
            pub = db.get(Publisher, p_id)
            if not pub:
                pub = db.query(Publisher).filter(Publisher.name == p_data["name"]).first()
            if not pub:
                pub = Publisher(
                    id=p_id,
                    name=p_data["name"],
                    contact_info=p_data.get("contact_info"),
                )
                db.add(pub)
                db.flush()
            publisher_map[str(p_id)] = pub
            publisher_map[pub.name] = pub
        db.commit()

        # 5. Yazarlar
        author_map = {}
        for a_data in data.get("authors", []):
            a_id = uuid.UUID(a_data["id"])
            author = db.get(Author, a_id)
            if not author:
                author = (
                    db.query(Author)
                    .filter(
                        Author.first_name == a_data["first_name"],
                        Author.last_name == a_data["last_name"],
                    )
                    .first()
                )
            if not author:
                author = Author(
                    id=a_id,
                    first_name=a_data["first_name"],
                    last_name=a_data["last_name"],
                )
                db.add(author)
                db.flush()
            author_map[str(a_id)] = author
        db.commit()

        # 6. Kategoriler
        category_map = {}
        for c_data in data.get("categories", []):
            c_name = c_data["name"]
            cat = db.query(Category).filter(Category.name == c_name).first()
            if not cat:
                cat = Category(id=c_data.get("id"), name=c_name)
                db.add(cat)
                db.flush()
            category_map[str(c_data.get("id"))] = cat
            category_map[c_name] = cat
        db.commit()

        # 7. Kitaplar
        added_books = 0
        for b_data in data.get("books", []):
            b_id = uuid.UUID(b_data["id"])
            existing_book = db.query(Book).filter(
                (Book.id == b_id) | (Book.isbn == b_data["isbn"])
            ).first()
            if existing_book:
                continue

            # Yayınevi eşleştir
            pub = None
            if b_data.get("publisher_id"):
                pub = publisher_map.get(str(b_data["publisher_id"]))

            # Yazarlar eşleştir
            b_authors = [
                author_map[aid] for aid in b_data.get("author_ids", []) if aid in author_map
            ]

            # Kategoriler eşleştir
            b_categories = [
                category_map[str(cid)]
                for cid in b_data.get("category_ids", [])
                if str(cid) in category_map
            ]

            book = Book(
                id=b_id,
                title=b_data["title"],
                isbn=b_data["isbn"],
                published_year=b_data.get("published_year"),
                stock_count=b_data.get("stock_count", 0),
                cover_url=b_data.get("cover_url"),
                publisher=pub,
                authors=b_authors,
                categories=b_categories,
            )
            db.add(book)
            added_books += 1

        db.commit()
        print(f"[SEED] Bulut veritabanı başarıyla dolduruldu! Toplam {added_books} kitap eklendi.")

    except Exception as e:
        db.rollback()
        print(f"[SEED HATA] Seed sırasında hata oluştu: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_cloud()
