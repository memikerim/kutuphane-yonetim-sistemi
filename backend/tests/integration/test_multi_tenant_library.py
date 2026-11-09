from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.modules.auth.models import Role, RoleName, User
from app.modules.catalog.models import Book
from app.modules.library.service import ensure_default_test_library_and_migrate


def _create_user_with_token(
    db: Session,
    email: str,
    first_name: str = "Üye",
    last_name: str = "Kullanıcı",
) -> tuple[User, dict[str, str]]:
    user_role = db.query(Role).filter_by(name=RoleName.USER).first()
    user = User(
        email=email,
        password_hash=hash_password("pass123456"),
        first_name=first_name,
        last_name=last_name,
        roles=[user_role] if user_role else [],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user_id=user.id, email=user.email, roles=["USER"])
    return user, {"Authorization": f"Bearer {token}"}


def test_default_test_library_migration_and_system_admin_upgrade(
    client: TestClient,
    db_session: Session,
    admin_user: User,
    test_user: User,
    test_book: Book,
):
    """
    1. Mevcut ADMIN kullanıcıları SYSTEM_ADMIN seviyesine yükseltilmeli.
    2. 'Test Kütüphanesi' (APPROVED) oluşturulmalı ve mevcut kitaplar + üyeler bağlanmalı.
    """
    test_lib = ensure_default_test_library_and_migrate(db_session)
    assert test_lib.name == "Test Kütüphanesi"
    assert test_lib.status == "APPROVED"
    assert float(test_lib.daily_fine_amount) == 5.0
    assert int(test_lib.max_borrow_days) == 14
    assert int(test_lib.max_books_per_user) == 3

    db_session.refresh(admin_user)
    db_session.refresh(test_book)
    assert admin_user.is_system_admin is True
    assert test_book.library_id == test_lib.id

    # Mevcut üyelerin Test Kütüphanesi üyeliği APPROVED olmalı
    res = client.get("/api/v1/libraries/my", headers={"Authorization": f"Bearer {create_access_token(user_id=test_user.id, email=test_user.email, roles=['USER'])}"})
    assert res.status_code == 200
    memberships = res.json()
    assert len(memberships) == 1
    assert memberships[0]["library_name"] == "Test Kütüphanesi"
    assert memberships[0]["status"] == "APPROVED"


def test_library_creation_request_and_system_admin_approval(
    client: TestClient,
    db_session: Session,
    admin_user: User,
    admin_headers: dict[str, str],
):
    """
    2. Herhangi bir kullanıcı yeni kütüphane talebi oluşturabilmeli (PENDING).
    SYSTEM_ADMIN onayladığında (APPROVED), oluşturan kullanıcı otomatik LIBRARY_ADMIN olmalı.
    """
    ensure_default_test_library_and_migrate(db_session)
    creator, creator_headers = _create_user_with_token(
        db_session, "kurucu@uni.edu.tr", "Ayşe", "Kurucu"
    )

    # Kullanıcı yeni kütüphane kurulum talebi gönderir
    create_res = client.post(
        "/api/v1/libraries",
        headers=creator_headers,
        json={
            "name": "Mühendislik Fakültesi Kütüphanesi",
            "description": "Mühendislik akademik yayınlar kütüphanesi",
            "daily_fine_amount": 7.5,
            "max_borrow_days": 21,
            "max_books_per_user": 4,
            "penalty_rules_text": "Geciken her gün için 7.5 TL ceza uygulanır.",
        },
    )
    assert create_res.status_code == 201
    resp_json = create_res.json()
    assert (
        resp_json["message"]
        == "Kütüphane oluşturma talebiniz Sistem Yöneticisi onayına gönderilmiştir. Onaylandığında bu kütüphanenin yöneticisi olacaksınız."
    )
    lib_data = resp_json["library"]
    lib_id = lib_data["id"]
    assert lib_data["status"] == "PENDING"
    assert float(lib_data["daily_fine_amount"]) == 7.5
    assert int(lib_data["max_borrow_days"]) == 21

    # SYSTEM_ADMIN bekleyen kütüphane taleplerini listeler ve onaylar
    list_res = client.get("/api/v1/system-admin/libraries?status=PENDING", headers=admin_headers)
    assert list_res.status_code == 200
    assert any(item["id"] == lib_id for item in list_res.json())

    approve_res = client.post(
        f"/api/v1/system-admin/libraries/{lib_id}/status",
        headers=admin_headers,
        json={"status": "APPROVED"},
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "APPROVED"

    # Kurucu kullanıcı otomatik olarak LIBRARY_ADMIN ve APPROVED olmalı
    my_mems = client.get("/api/v1/libraries/my", headers=creator_headers).json()
    eng_mem = next((m for m in my_mems if m["library_id"] == lib_id), None)
    assert eng_mem is not None
    assert eng_mem["role"] == "LIBRARY_ADMIN"
    assert eng_mem["status"] == "APPROVED"


def test_membership_application_ban_role_delegation_and_tenant_isolation(
    client: TestClient,
    db_session: Session,
    admin_headers: dict[str, str],
):
    """
    3 & 4 & 6. Kütüphane ismiyle katılım başvurusu, LIBRARY_ADMIN onayı, banlama,
    LIBRARY_ADMIN yetki devri, tam veri izolasyonu ve kütüphaneye özel ceza/ödünç kuralları.
    """
    test_lib = ensure_default_test_library_and_migrate(db_session)

    # A Kütüphanesi ve Yöneticisi
    admin_a, headers_a = _create_user_with_token(db_session, "admin_a@lib.org", "Ahmet", "YöneticiA")
    res_lib_a = client.post(
        "/api/v1/libraries",
        headers=headers_a,
        json={
            "name": "Merkez Şehir Kütüphanesi",
            "description": "A Kütüphanesi",
            "daily_fine_amount": 8.0,
            "max_borrow_days": 10,
            "max_books_per_user": 2,
        },
    )
    lib_a_id = res_lib_a.json()["library"]["id"]
    client.post(
        f"/api/v1/system-admin/libraries/{lib_a_id}/status",
        headers=admin_headers,
        json={"status": "APPROVED"},
    )

    # B Kütüphanesi ve Yöneticisi
    admin_b, headers_b = _create_user_with_token(db_session, "admin_b@lib.org", "Burak", "YöneticiB")
    res_lib_b = client.post(
        "/api/v1/libraries",
        headers=headers_b,
        json={
            "name": "Bilim Sanat Kütüphanesi",
            "description": "B Kütüphanesi",
            "daily_fine_amount": 12.0,
            "max_borrow_days": 7,
            "max_books_per_user": 1,
        },
    )
    lib_b_id = res_lib_b.json()["library"]["id"]
    client.post(
        f"/api/v1/system-admin/libraries/{lib_b_id}/status",
        headers=admin_headers,
        json={"status": "APPROVED"},
    )

    # TAM VERİ İZOLASYONU: A kütüphanesi yöneticisi B kütüphanesinin ayarlarına veya üyelerine erişemez!
    forbidden_settings = client.put(
        f"/api/v1/libraries/{lib_b_id}/settings",
        headers=headers_a,
        json={"daily_fine_amount": 99.0},
    )
    assert forbidden_settings.status_code == 403

    forbidden_members = client.get(
        f"/api/v1/libraries/{lib_b_id}/members",
        headers=headers_a,
    )
    assert forbidden_members.status_code == 403

    # A Kütüphanesi yöneticisi kendi kütüphanesine kitap ekler (B kütüphanesine ekleyemez)
    forbidden_book = client.post(
        "/api/v1/books",
        headers=headers_a,
        json={
            "title": "Yetkisiz Kitap",
            "isbn": "9789750000999",
            "published_year": 2024,
            "stock_count": 2,
            "library_id": lib_b_id,
        },
    )
    assert forbidden_book.status_code == 403

    book_a_res = client.post(
        "/api/v1/books",
        headers=headers_a,
        json={
            "title": "A Kütüphanesi Özel Kitabı",
            "isbn": "9789750000111",
            "published_year": 2024,
            "stock_count": 3,
            "library_id": lib_a_id,
        },
    )
    assert book_a_res.status_code == 201
    book_a_id = book_a_res.json()["id"]
    assert book_a_res.json()["library_name"] == "Merkez Şehir Kütüphanesi"
    assert float(book_a_res.json()["library_daily_fine_amount"]) == 8.0

    # Yeni kayıt olan öğrenci kütüphane ismiyle ("Merkez Şehir Kütüphanesi") katılım başvurusu yapar
    student, student_headers = _create_user_with_token(
        db_session, "ogrenci@uni.edu.tr", "Zeynep", "Öğrenci"
    )
    apply_res = client.post(
        "/api/v1/libraries/apply",
        headers=student_headers,
        json={
            "library_name": "Merkez Şehir Kütüphanesi",
            "phone": "0555 987 65 43",
            "identity_or_student_no": "20260001",
            "department_or_address": "Bilgisayar Mühendisliği",
            "application_note": "Tez araştırması için katılmak istiyorum.",
        },
    )
    assert apply_res.status_code == 201
    membership_id = apply_res.json()["id"]
    assert apply_res.json()["status"] == "PENDING"

    # Başvuru henüz PENDING iken öğrenci bu kütüphaneden kitap ödünç alamaz (403)
    borrow_before_approval = client.post(
        "/api/v1/borrowings",
        headers=student_headers,
        json={"book_id": book_a_id},
    )
    assert borrow_before_approval.status_code == 403

    # A Kütüphanesi yöneticisi başvuruyu görür ve onaylar (APPROVED)
    members_list = client.get(f"/api/v1/libraries/{lib_a_id}/members", headers=headers_a).json()
    student_mem = next(m for m in members_list if m["id"] == membership_id)
    assert student_mem["phone"] == "0555 987 65 43"
    assert student_mem["identity_or_student_no"] == "20260001"

    approve_mem_res = client.post(
        f"/api/v1/libraries/{lib_a_id}/members/{membership_id}/status",
        headers=headers_a,
        json={"status": "APPROVED"},
    )
    assert approve_mem_res.status_code == 200
    assert approve_mem_res.json()["status"] == "APPROVED"

    # Onaylandıktan sonra öğrenci kitabı ödünç alabilir; due_date kütüphanenin max_borrow_days (10 gün) kuralına göre hesaplanır!
    borrow_res = client.post(
        "/api/v1/borrowings",
        headers=student_headers,
        json={"book_id": book_a_id},
    )
    assert borrow_res.status_code == 201
    expected_due = (date.today() + timedelta(days=10)).isoformat()
    assert borrow_res.json()["due_date"] == expected_due
    assert float(borrow_res.json()["library_daily_fine"]) == 8.0

    # A Kütüphanesi yöneticisi öğrenciyi banlarsa (BANNED), öğrenci artık bu kütüphanede işlem yapamaz
    ban_res = client.post(
        f"/api/v1/libraries/{lib_a_id}/members/{membership_id}/status",
        headers=headers_a,
        json={"status": "BANNED", "ban_reason": "Kütüphane kuralları ihlali"},
    )
    assert ban_res.status_code == 200
    assert ban_res.json()["status"] == "BANNED"

    # Ban kaldırılır (APPROVED) ve üyeye LIBRARY_ADMIN yetkisi devredilir
    client.post(
        f"/api/v1/libraries/{lib_a_id}/members/{membership_id}/status",
        headers=headers_a,
        json={"status": "APPROVED"},
    )
    promote_res = client.post(
        f"/api/v1/libraries/{lib_a_id}/members/{membership_id}/role",
        headers=headers_a,
        json={"role": "LIBRARY_ADMIN"},
    )
    assert promote_res.status_code == 200
    assert promote_res.json()["role"] == "LIBRARY_ADMIN"

    # Yetki devri sonrası yeni yönetici (student) A kütüphanesinin ceza ayarlarını güncelleyebilir
    update_settings_res = client.put(
        f"/api/v1/libraries/{lib_a_id}/settings",
        headers=student_headers,
        json={"daily_fine_amount": 15.0, "max_borrow_days": 12},
    )
    assert update_settings_res.status_code == 200
    assert float(update_settings_res.json()["daily_fine_amount"]) == 15.0
    assert int(update_settings_res.json()["max_borrow_days"]) == 12

