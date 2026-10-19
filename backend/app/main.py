from fastapi import FastAPI

import app.models  # noqa: F401  - tüm modelleri/ilişkileri mapper'a kaydeder
from app.core.config import settings
from app.core.logging_config import setup_logging
from app.modules.admin.router import router as admin_router
from app.modules.auth.router import router as auth_router
from app.modules.borrowing.router import router as borrowing_router
from app.modules.catalog.router import router as catalog_router
from app.modules.review.router import router as review_router

# Uygulama genelinde loglamayı başlat
setup_logging()

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

API_PREFIX = "/api/v1"
app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(admin_router, prefix=API_PREFIX)
app.include_router(catalog_router, prefix=API_PREFIX)
app.include_router(borrowing_router, prefix=API_PREFIX)
app.include_router(review_router, prefix=API_PREFIX)


@app.get("/health", tags=["health"], summary="Sistem sağlık kontrolü")
def health() -> dict[str, str]:
    """Sistemin ve API servisinin ayakta olduğunu doğrular."""
    return {"status": "ok"}
