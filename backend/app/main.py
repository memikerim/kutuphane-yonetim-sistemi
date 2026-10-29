import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy import text

import app.models  # noqa: F401  - tüm modelleri/ilişkileri mapper'a kaydeder
from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.core.logging_config import setup_logging
from app.modules.admin.router import router as admin_router
from app.modules.auth.router import router as auth_router
from app.modules.borrowing.router import router as borrowing_router
from app.modules.borrowing.service import sync_overdue_borrowings, sync_reservations
from app.modules.catalog.router import router as catalog_router
from app.modules.review.router import router as review_router

# Uygulama genelinde loglamayı başlat
setup_logging()
logger = logging.getLogger("app.main")


def ensure_database_schema() -> None:
    """Veritabanı tablolarındaki eksik sütunları güvenli şekilde oluşturur (PostgreSQL/SQLite uyumlu)."""
    try:
        from app.modules.borrowing.models import StockMovement
        StockMovement.__table__.create(bind=engine, checkfirst=True)
    except Exception as e:
        logger.warning(f"StockMovement tablo kontrolü uyarısı: {e}")

    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE borrowings ADD COLUMN IF NOT EXISTS approval_status VARCHAR(30) DEFAULT 'APPROVED' NOT NULL"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE borrowings ADD COLUMN IF NOT EXISTS return_condition VARCHAR(20) DEFAULT 'GOOD' NOT NULL"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE borrowings ADD COLUMN IF NOT EXISTS damage_penalty FLOAT DEFAULT 0.0 NOT NULL"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE borrowings ADD COLUMN IF NOT EXISTS return_notes VARCHAR(500)"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE borrowings ADD COLUMN IF NOT EXISTS admin_notes VARCHAR(500)"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE borrowings ADD COLUMN IF NOT EXISTS penalty_payment_status VARCHAR(30) DEFAULT 'UNPAID' NOT NULL"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE borrowings ADD COLUMN IF NOT EXISTS penalty_paid_at TIMESTAMP WITH TIME ZONE"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE borrowings ADD COLUMN IF NOT EXISTS is_rejection_read BOOLEAN DEFAULT FALSE NOT NULL"
                )
            )
            conn.execute(
                text(
                    "UPDATE borrowings SET penalty_payment_status = 'PAID' WHERE is_penalty_paid = true AND penalty_payment_status = 'UNPAID'"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_banned BOOLEAN DEFAULT FALSE NOT NULL"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS ban_reason VARCHAR(500)"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS banned_at TIMESTAMP WITH TIME ZONE"
                )
            )
    except Exception as e:
        logger.warning(f"Şema doğrulama/güncelleme uyarısı: {e}")


# Modül yüklenirken şemayı hemen garanti altına al
if not settings.DATABASE_URL.startswith("sqlite"):
    ensure_database_schema()


async def _periodic_reservation_and_overdue_sync() -> None:
    """Kullanıcılar giriş yapmasa bile arka planda düzenli olarak süresi dolan
    rezervasyonları düşürür ve sıradaki kullanıcının 24 saatlik sayacını başlatır."""
    while True:
        try:
            await asyncio.sleep(15)
            with SessionLocal() as db:
                sync_overdue_borrowings(db)
                sync_reservations(db)
        except asyncio.CancelledError:
            break
        except Exception:
            pass


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if not getattr(_app.state, "testing", False):
        need_seed = False
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1 FROM books LIMIT 1"))
        except Exception:
            need_seed = True

        if need_seed:
            try:
                from app.seed_cloud import seed_cloud
                seed_cloud()
            except Exception as e:
                logger.warning(f"Otomatik şema ve tohumlama sırasında hata: {e}")
        else:
            ensure_database_schema()

    sync_task = None
    if not getattr(_app.state, "testing", False):
        import os
        if not os.getenv("VERCEL"):
            sync_task = asyncio.create_task(_periodic_reservation_and_overdue_sync())

    try:
        yield
    finally:
        if sync_task:
            sync_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await sync_task


tags_metadata = [
    {
        "name": "Auth",
        "description": "Kullanıcı kaydı, JWT ile kimlik doğrulama ve profil bilgisi endpoint'leri.",
    },
    {
        "name": "Catalog",
        "description": "Yazarlar, Kategoriler, Yayınevleri ve Kitaplar için CRUD işlemleri, arama, filtreleme ve sayfalama.",
    },
    {
        "name": "Borrowing & Reservations",
        "description": "Kitap ödünç alma, iade süreçleri ve rezervasyon kuyruğu (Atomik transaction ve veritabanı kısıtlamaları korumalı).",
    },
    {
        "name": "Review & Rating",
        "description": "Kitaplara 1-5 arası puan verme ve yorum yapma sistemi (Kullanıcı başına tekil yorum kuralı).",
    },
    {
        "name": "Admin",
        "description": "Yalnızca ADMIN rolüne sahip yöneticiler için ayrılmış yönetimsel uç noktalar.",
    },
    {
        "name": "health",
        "description": "Sistem canlılık ve sağlık kontrolü (Liveness / Readiness probe).",
    },
]

app = FastAPI(
    title=f"{settings.APP_NAME} API",
    lifespan=lifespan,
    description="""
## Kütüphane Yönetim Sistemi API Dokümantasyonu

Bu API, FastAPI ve PostgreSQL (SQLAlchemy 2.0 & Alembic) mimarisiyle geliştirilmiş kurumsal seviyede bir kütüphane yönetim platformudur.

### Temel Özellikler
* **Sprint 1 - Altyapı & Şema:** PostgreSQL 15, UUID birincil anahtarlar, çoktan-çoğa ilişkiler ve veri bütünlüğü kısıtlamaları (constraints).
* **Sprint 2 - Auth & RBAC:** Passlib/Bcrypt ile güvenli şifre hashleme, Python-Jose ile JWT Access Token yönetimi ve Rol Tabanlı Yetkilendirme (USER/ADMIN).
* **Sprint 3 - Katalog Yönetimi:** Kitap, Yazar, Kategori ve Yayınevi CRUD operasyonları.
* **Sprint 4 - Arama & Filtreleme:** Başlık/açıklama arama, çoklu filtreleme, dinamik sıralama ve sayfalama (pagination).
* **Sprint 5 - Ödünç & Rezervasyon:** Sıfır stok kontrolü, eşzamanlı işlem (race condition) koruması, tekil rezervasyon kısıtlaması ve atomik transaction yönetimi.
* **Sprint 6 - Değerlendirme, Loglama & Test:** 1-5 puanlı yorum sistemi, Python structured logging, Pytest birim & entegrasyon testleri.

### Yetkilendirme
Korumalı endpoint'lere erişmek için **Authorize** butonunu kullanarak `/api/v1/auth/login` üzerinden temin ettiğiniz JWT token'ı (`Bearer <token>`) giriniz.
    """,
    version="1.0.0",
    openapi_tags=tags_metadata,
    swagger_ui_parameters={"persistAuthorization": True},
    contact={
        "name": "Kütüphane Yönetim Sistemi Ekibi",
        "url": "https://github.com/library-system",
    },
    license_info={
        "name": "MIT License",
    },
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_origin_regex=r"https://.*\.vercel\.app|https://.*\.hf\.space|http://localhost:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api/v1"
app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(admin_router, prefix=API_PREFIX)
app.include_router(catalog_router, prefix=API_PREFIX)
app.include_router(borrowing_router, prefix=API_PREFIX)
app.include_router(review_router, prefix=API_PREFIX)


@app.get("/", include_in_schema=False)
def root():
    """Kök dizine girildiğinde doğrudan Swagger dokümantasyonuna yönlendirir."""
    return RedirectResponse(url="/docs")


@app.get("/health", tags=["health"], summary="Sistem sağlık kontrolü")
def health() -> dict[str, str]:
    """Sistemin ve API servisinin ayakta olduğunu doğrular."""
    return {"status": "ok"}


@app.get("/api/v1/migrate-db", include_in_schema=False)
def trigger_migrate_db():
    ensure_database_schema()
    return {"status": "ok", "message": "Database schema checked and verified"}
