# 📚 Kütüphane Yönetim Sistemi (Full-Stack: FastAPI + React & Tailwind CSS)

FastAPI, SQLAlchemy 2.0, PostgreSQL 15, Alembic, React (Vite + Tailwind CSS) ve Docker kullanılarak 6 Sprintlik çevik (Agile) yazılım geliştirme metodolojisiyle geliştirilmiş, **%100 Responsive (Mobil, Tablet, Masaüstü uyumlu)** kurumsal bir Kütüphane Yönetim Sistemi projesidir.

---

## 🚀 Mimari ve Sprint Özeti

| Aşama | Kapsam | Öne Çıkan Teknik Özellikler |
| :--- | :--- | :--- |
| **Sprint 1** | Analiz, Veritabanı Tasarımı & Altyapı | Docker Compose (PostgreSQL 15, FastAPI Backend, React Frontend), Modüler Mimari (`auth`, `catalog`, `borrowing`, `review`), UUID PK, Çoktan-Çoğa İlişkiler, Alembic Migration |
| **Sprint 2** | Authentication & Authorization | `passlib[bcrypt]` ile şifreleme, `python-jose` ile JWT (`sub`, `email`, `roles`), RBAC (`require_roles(["ADMIN"])`), `get_current_user` Guard |
| **Sprint 3** | Temel Katalog Yönetimi | Yazar (`Author`), Kategori (`Category`), Yayınevi (`Publisher`) ve Kitap (`Book`) CRUD operasyonları, Ara tablo (`BookAuthors`, `BookCategories`) yönetimi |
| **Sprint 4** | Arama, Filtreleme & Sayfalama | `GET /api/v1/books` üzerinde dinamik filtreleme (`search`, `category`, `author`, `publisher`), sıralama (`sortBy`, `sortOrder`) ve sayfalama (`page`, `limit`) |
| **Sprint 5** | Ödünç Alma (Borrowing) & Rezervasyon | Atomik Transaction yönetimi, eşzamanlılık (Race Condition) korumalı stok düşümü/artırımı, Partial Unique Index ile mükerrer `PENDING` rezervasyon engeli |
| **Sprint 6** | Değerlendirme (Review), Loglama & Test | 1-5 arası puanlama & tekil yorum kısıtlaması (`uq_reviews_user_book`), Structured Logging, 61 adet Unit/Integration/Constraint Pytest testi ve OpenAPI dokümantasyonu |
| **Frontend** | %100 Responsive Modern Web Arayüzü | React 18 + Vite + Tailwind CSS + Lucide Icons; Mobil Hamburger Drawer, Esnek Grid, Mobil Filtre Çekmecesi, Kitap Detay/Ödünç/Yorum Modalı ve Admin CRUD Paneli |

---

## 🛠️ Kurulum ve Çalıştırma (Docker ile - Önerilen)

Projeyi kendi bilgisayarınızda tek komutla ayağa kaldırmak için **Docker Desktop** kurulu olması yeterlidir.

### 1. Çevresel Değişkenleri Hazırlayın
Proje kök dizinindeki `.env.example` dosyasını `.env` olarak kopyalayın:
```bash
cp .env.example .env
```

### 2. Tüm Servisleri (DB + Backend + Frontend) Başlatın
```bash
docker-compose up -d --build
```

### 3. Uygulama Adresleri
Konteynerler ayağa kalktığında tarayıcınızdan aşağıdaki adreslere erişebilirsiniz:
- **🌐 Web Arayüzü (React Frontend):** [http://localhost:5173](http://localhost:5173)
- **📑 Swagger UI (API Dokümantasyonu):** [http://localhost:8000/docs](http://localhost:8000/docs)
- **📘 ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **🩺 Health Check:** [http://localhost:8000/health](http://localhost:8000/health)

---

## 💻 Frontend'i Yerel Olarak Çalıştırma (Alternatif)

Eğer Frontend'i Docker dışında doğrudan Node.js ile çalıştırmak isterseniz:
```bash
cd frontend
npm install
npm run dev
```
Tarayıcınızdan `http://localhost:5173` adresine gidebilirsiniz.

---

## 🔑 Kullanıcı Kaydı ve Admin Yetkisi Verme

1. Web arayüzünden (`http://localhost:5173`) sağ üstteki **Kayıt Ol** butonuyla yeni bir hesap oluşturun (Varsayılan olarak `USER` rolü atanır).
2. Kaydettiğiniz kullanıcıya `ADMIN` rolü vermek için terminalde aşağıdaki CLI komutunu çalıştırın:
```bash
docker-compose exec backend python -m app.cli make-admin kullanici@ornek.com
```
3. Web arayüzünde çıkış yapıp tekrar giriş yaptığınızda üst menüde **ADMIN** rozeti ve **Admin Paneli** sekmesi otomatik olarak aktif olacaktır.

---

## 🧪 Otomatik Testlerin Çalıştırılması (Pytest)

Projede birim (unit), entegrasyon (integration) ve veritabanı kısıtlamalarını (constraints: negatif stok engeli, 1-5 puan sınırı, tarih kuralları, tekillik kısıtlamaları) doğrulayan **61 adet otomatik test** bulunmaktadır.

```bash
# Docker üzerinden:
docker-compose exec backend pytest -v

# Veya yerel Python sanal ortamı üzerinden:
& "backend/.venv/Scripts/pytest.exe" -v
```

---

## 📂 Proje Klasör Yapısı

```text
kutuphane-yonetim-sistemi/
├── docker-compose.yml          # PostgreSQL 15, FastAPI Backend ve React Frontend servisleri
├── .env.example                # Örnek çevresel değişken şablonu
├── pytest.ini                  # Pytest yapılandırması
├── frontend/                   # %100 Responsive React + Vite + Tailwind CSS Arayüzü
│   ├── Dockerfile
│   ├── package.json
│   ├── tailwind.config.js
│   └── src/
│       ├── api.js              # JWT destekli merkezi REST API istemcisi
│       ├── App.jsx             # Katalog Vitrini, Dinamik Filtreleme, Sayfalama & Toast
│       └── components/
│           ├── Navbar.jsx          # Masaüstü Navbar & Mobil Hamburger Drawer Menü
│           ├── AuthModal.jsx       # Giriş Yap & Kayıt Ol Modalı
│           ├── BookDetailModal.jsx # Ödünç Al, Rezerve Et & 1-5 Yıldız Yorum Modalı
│           ├── MyLibraryView.jsx   # Ödünç Kitaplarım (İade Et) & Rezervasyonlarım
│           └── AdminPanel.jsx      # Çoklu Yazar/Kategori Seçimli Admin CRUD Paneli
└── backend/
    ├── Dockerfile
    ├── alembic.ini
    ├── requirements.txt
    ├── alembic/                # Veritabanı şema göçleri (Migrations)
    ├── app/
    │   ├── main.py             # FastAPI uygulama girişi, CORS ve OpenAPI ayarları
    │   ├── cli.py              # Yönetimsel CLI komutları (make-admin vb.)
    │   ├── core/               # Config, Database, Security (JWT/Bcrypt), Logging
    │   └── modules/
    │       ├── auth/           # Kullanıcı, Rol, Login/Register, RBAC Dependencies
    │       ├── catalog/        # Kitap, Yazar, Kategori, Yayınevi, Arama & Sayfalama
    │       ├── borrowing/      # Ödünç Alma, İade ve Rezervasyon Sistemi
    │       ├── review/         # Kitap Puanlama (1-5) ve Yorum Sistemi
    │       └── admin/          # Admin Dashboard / Yönetici Uç Noktaları
    └── tests/                  # 61 Adet Unit, Constraint ve Integration Testi
```
