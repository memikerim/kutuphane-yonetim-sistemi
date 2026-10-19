# 📚 Kütüphane Yönetim Sistemi (Library Management System API)

FastAPI, SQLAlchemy 2.0, PostgreSQL 15, Alembic ve Docker kullanılarak 6 Sprintlik çevik (Agile) yazılım geliştirme metodolojisiyle geliştirilmiş kurumsal bir Kütüphane Yönetim Sistemi REST API projesidir.

---

## 🚀 Mimari ve Sprint Özeti

| Sprint | Kapsam | Öne Çıkan Teknik Özellikler |
| :--- | :--- | :--- |
| **Sprint 1** | Analiz, Veritabanı Tasarımı & Altyapı | Docker Compose (PostgreSQL 15 & Backend), Modüler Mimari (`auth`, `catalog`, `borrowing`, `review`), UUID PK, Çoktan-Çoğa İlişkiler, Alembic Migration |
| **Sprint 2** | Authentication & Authorization | `passlib[bcrypt]` ile şifreleme, `python-jose` ile JWT (`sub`, `email`, `roles`), RBAC (`require_roles(["ADMIN"])`), `get_current_user` Guard |
| **Sprint 3** | Temel Katalog Yönetimi | Yazar (`Author`), Kategori (`Category`), Yayınevi (`Publisher`) ve Kitap (`Book`) CRUD operasyonları, Ara tablo (`BookAuthors`, `BookCategories`) yönetimi |
| **Sprint 4** | Arama, Filtreleme & Sayfalama | `GET /api/v1/books` üzerinde dinamik filtreleme (`search`, `category`, `author`, `publisher`), sıralama (`sortBy`, `sortOrder`) ve sayfalama (`page`, `limit`) |
| **Sprint 5** | Ödünç Alma (Borrowing) & Rezervasyon | Atomik Transaction yönetimi, eşzamanlılık (Race Condition) korumalı stok düşümü/artırımı, Partial Unique Index ile mükerrer `PENDING` rezervasyon engeli |
| **Sprint 6** | Değerlendirme (Review), Loglama & Test | 1-5 arası puanlama & tekil yorum kısıtlaması (`uq_reviews_user_book`), Structured Logging, 60 adet Unit/Integration/Constraint Pytest testi ve OpenAPI dokümantasyonu |

---

## 🛠️ Kurulum ve Çalıştırma (Docker ile - Önerilen)

Projeyi kendi bilgisayarınızda tek komutla ayağa kaldırmak için **Docker** ve **Docker Compose** kurulu olması yeterlidir.

### 1. Çevresel Değişkenleri Hazırlayın
Proje kök dizinindeki `.env.example` dosyasını `.env` olarak kopyalayın:
```bash
cp .env.example .env
```

### 2. Konteynerleri Başlatın
```bash
docker compose up -d --build
```

### 3. Veritabanı Tablolarını Oluşturun (Migration)
```bash
docker compose exec backend alembic upgrade head
```

### 4. Swagger UI (API Dokümantasyonu)
Tarayıcınızdan aşağıdaki adrese giderek tüm uç noktaları inceleyebilir ve canlı test edebilirsiniz:
- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health Check:** [http://localhost:8000/health](http://localhost:8000/health)

---

## 🔑 Kullanıcı Kaydı ve Admin Yetkisi Verme

1. `POST /api/v1/auth/register` uç noktasından yeni bir kullanıcı kaydedin (Varsayılan olarak `USER` rolü atanır).
2. Kaydettiğiniz kullanıcıya `ADMIN` rolü vermek için aşağıdaki CLI komutunu çalıştırın:
```bash
docker compose exec backend python -m app.cli make-admin kullanici@ornek.com
```
3. `POST /api/v1/auth/login` üzerinden giriş yaparak aldığınız JWT `access_token` değerini Swagger sağ üstteki **Authorize** butonuna yapıştırın.

---

## 🧪 Testlerin Çalıştırılması (Pytest)

Projede birim (unit), entegrasyon (integration) ve veritabanı kısıtlamalarını (constraints: negatif stok engeli, 1-5 puan sınırı, tarih kuralları, tekillik kısıtlamaları) doğrulayan **60 adet otomatik test** bulunmaktadır.

### Docker Üzerinden Çalıştırma:
```bash
docker compose exec backend pytest -v
```

### Yerel Sanal Ortam (Virtualenv) Üzerinden Çalıştırma:
```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
pytest -v
```

---

## 📂 Proje Klasör Yapısı

```text
kutuphane-yonetim-sistemi/
├── docker-compose.yml          # PostgreSQL 15 ve FastAPI Backend编排
├── .env.example                # Örnek çevresel değişken şablonu
├── pytest.ini                  # Pytest yapılandırması
└── backend/
    ├── Dockerfile
    ├── alembic.ini
    ├── requirements.txt
    ├── alembic/                # Veritabanı şema göçleri (Migrations)
    ├── app/
    │   ├── main.py             # FastAPI uygulama girişi ve OpenAPI ayarları
    │   ├── cli.py              # Yönetimsel CLI komutları (make-admin vb.)
    │   ├── core/               # Config, Database, Security (JWT/Bcrypt), Logging
    │   └── modules/
    │       ├── auth/           # Kullanıcı, Rol, Login/Register, RBAC Dependencies
    │       ├── catalog/        # Kitap, Yazar, Kategori, Yayınevi, Arama & Sayfalama
    │       ├── borrowing/      # Ödünç Alma, İade ve Rezervasyon Sistemi
    │       ├── review/         # Kitap Puanlama (1-5) ve Yorum Sistemi
    │       └── admin/          # Admin Dashboard / Yönetici Uç Noktaları
    └── tests/
        ├── conftest.py         # İzole In-Memory Test DB ve Fixture'lar
        ├── unit/               # Auth, Borrowing ve DB Constraint Birim Testleri
        └── integration/        # Auth, Borrowing ve Review Endpoint Entegrasyon Testleri
```

