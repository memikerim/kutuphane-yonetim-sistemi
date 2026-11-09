from datetime import date
import logging
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.auth.models import Role, RoleName, User
from app.modules.borrowing.models import Borrowing, BorrowingStatus, Reservation, StockMovement
from app.modules.catalog.models import Book
from app.modules.library.models import (
    Library,
    LibraryMembership,
    LibraryStatus,
    MembershipRole,
    MembershipStatus,
)
from app.modules.library.schemas import (
    LibraryCreate,
    LibraryCreateResponse,
    LibraryMembershipApplyRequest,
    LibraryMembershipRead,
    LibraryMembershipRoleUpdate,
    LibraryMembershipStatusUpdate,
    LibraryRead,
    LibrarySettingsUpdate,
)

logger = logging.getLogger(__name__)

DEFAULT_TEST_LIBRARY_NAME = "Test Kütüphanesi"
DEFAULT_TEST_LIBRARY_DESC = (
    "Mevcut tüm katalog kitaplarının, ödünç kayıtlarının ve üyelerin bağlı olduğu varsayılan merkez kütüphane."
)
DEFAULT_PENALTY_RULES_TEXT = (
    "Ödünç alınan kitapların teslim süresi içerisinde sağlam olarak kütüphane bankosuna iade edilmesi zorunludur. "
    "Zamanında teslim edilmeyen her kitap için kütüphane tarafından belirlenen günlük gecikme cezası (TL) uygulanır."
)
LIBRARY_CREATE_PENDING_MESSAGE = (
    "Kütüphane oluşturma talebiniz Sistem Yöneticisi onayına gönderilmiştir. "
    "Onaylandığında bu kütüphanenin yöneticisi olacaksınız."
)


class NotFoundError(Exception):
    pass


class BusinessRuleError(Exception):
    pass


class ForbiddenError(Exception):
    pass


def _ensure_role(db: Session, role_name: RoleName) -> Role:
    role = db.scalar(select(Role).where(Role.name == role_name))
    if not role:
        role = Role(name=role_name)
        db.add(role)
        db.flush()
    return role


def is_user_system_admin(user: User | None) -> bool:
    if not user:
        return False
    return user.has_role(RoleName.SYSTEM_ADMIN) or user.has_role(RoleName.ADMIN)


def is_user_library_admin(db: Session, user: User | None, library_id: uuid.UUID) -> bool:
    if not user:
        return False
    if is_user_system_admin(user):
        return True
    membership = db.scalar(
        select(LibraryMembership).where(
            LibraryMembership.user_id == user.id,
            LibraryMembership.library_id == library_id,
            LibraryMembership.role == MembershipRole.LIBRARY_ADMIN.value,
            LibraryMembership.status == MembershipStatus.APPROVED.value,
        )
    )
    return membership is not None


def get_user_managed_library_ids(db: Session, user: User | None) -> list[uuid.UUID]:
    if not user:
        return []
    if is_user_system_admin(user):
        return list(db.scalars(select(Library.id)).all())
    return list(
        db.scalars(
            select(LibraryMembership.library_id).where(
                LibraryMembership.user_id == user.id,
                LibraryMembership.role == MembershipRole.LIBRARY_ADMIN.value,
                LibraryMembership.status == MembershipStatus.APPROVED.value,
            )
        ).all()
    )


def require_library_admin_access(db: Session, user: User, library_id: uuid.UUID) -> Library:
    library = db.get(Library, library_id)
    if not library:
        raise NotFoundError("Kütüphane bulunamadı")
    if not is_user_library_admin(db, user, library_id):
        raise ForbiddenError(
            "Bu kütüphanenin yönetim verilerine veya ayarlarına erişim yetkiniz bulunmamaktadır (Tam Veri İzolasyonu)."
        )
    return library


def require_system_admin_access(user: User) -> None:
    if not is_user_system_admin(user):
        raise ForbiddenError("Bu işlem yalnızca Sistem Yöneticisi (SYSTEM_ADMIN) tarafından gerçekleştirilebilir.")


def ensure_default_test_library_and_migrate(db: Session) -> Library:
    """
    1. Tüm rolleri (USER, ADMIN, LIBRARY_ADMIN, SYSTEM_ADMIN) garanti eder.
    2. Mevcut ADMIN kullanıcılarını otomatik olarak SYSTEM_ADMIN seviyesine yükseltir.
    3. 'Test Kütüphanesi' yoksa APPROVED durumunda oluşturur.
    4. library_id sütunu boş olan tüm kitapları, ödünçleri, rezervasyonları ve stok hareketlerini
       'Test Kütüphanesi'ne bağlar.
    5. Mevcut yöneticileri 'Test Kütüphanesi'nin LIBRARY_ADMIN'i yapar ve başlangıç/mevcut üyeleri
       APPROVED statüsüyle 'Test Kütüphanesi'ne bağlar.
    """
    role_user = _ensure_role(db, RoleName.USER)
    role_admin = _ensure_role(db, RoleName.ADMIN)
    role_lib_admin = _ensure_role(db, RoleName.LIBRARY_ADMIN)
    role_sys_admin = _ensure_role(db, RoleName.SYSTEM_ADMIN)
    db.flush()

    # Mevcut ADMIN kullanıcılarını SYSTEM_ADMIN seviyesine yükselt
    all_users = list(db.scalars(select(User)).all())
    primary_admin: User | None = None
    for u in all_users:
        if u.has_role(RoleName.ADMIN) or u.has_role(RoleName.SYSTEM_ADMIN):
            if not u.has_role(RoleName.SYSTEM_ADMIN):
                u.roles.append(role_sys_admin)
            if not u.has_role(RoleName.LIBRARY_ADMIN):
                u.roles.append(role_lib_admin)
            if primary_admin is None or u.email == "erimmemik@gmail.com":
                primary_admin = u
    db.flush()

    # Test Kütüphanesi kontrolü ve oluşturulması
    test_lib = db.scalar(select(Library).where(Library.name == DEFAULT_TEST_LIBRARY_NAME))
    is_first_migration = False
    if not test_lib:
        is_first_migration = True
        test_lib = Library(
            name=DEFAULT_TEST_LIBRARY_NAME,
            description=DEFAULT_TEST_LIBRARY_DESC,
            status=LibraryStatus.APPROVED.value,
            created_by_id=primary_admin.id if primary_admin else None,
            daily_fine_amount=5.0,
            max_borrow_days=14,
            max_books_per_user=3,
            penalty_rules_text=DEFAULT_PENALTY_RULES_TEXT,
        )
        db.add(test_lib)
        db.flush()
    else:
        if test_lib.status != LibraryStatus.APPROVED.value:
            test_lib.status = LibraryStatus.APPROVED.value
        if test_lib.created_by_id is None and primary_admin is not None:
            test_lib.created_by_id = primary_admin.id

    existing_membership_count = (
        db.scalar(select(func.count()).select_from(LibraryMembership)) or 0
    )
    if existing_membership_count == 0:
        is_first_migration = True

    # Boş library_id alanlarını Test Kütüphanesi ile doldur
    db.execute(
        update(Book).where(Book.library_id.is_(None)).values(library_id=test_lib.id)
    )
    db.execute(
        update(Borrowing).where(Borrowing.library_id.is_(None)).values(library_id=test_lib.id)
    )
    db.execute(
        update(Reservation).where(Reservation.library_id.is_(None)).values(library_id=test_lib.id)
    )
    db.execute(
        update(StockMovement).where(StockMovement.library_id.is_(None)).values(library_id=test_lib.id)
    )

    # Bilinen varsayılan kullanıcı e-postaları (seed / mevcut kullanıcılar)
    legacy_seed_emails = {
        "erimmemik@gmail.com",
        "ali@kutuphane.com",
        "ayse@ornek.com",
        "mehmet@ornek.com",
        "zeynep@ornek.com",
        "test@test.com",
    }

    # Aktif ödünç veya rezervasyon kaydı bulunan kullanıcılar (mevcut üyeler)
    users_with_history = set(
        db.scalars(select(Borrowing.user_id)).all()
    ) | set(
        db.scalars(select(Reservation.user_id)).all()
    )

    for u in all_users:
        is_admin_user = u.has_role(RoleName.SYSTEM_ADMIN) or u.has_role(RoleName.ADMIN)
        should_link = (
            is_first_migration
            or is_admin_user
            or (u.email and u.email.lower() in legacy_seed_emails)
            or (u.id in users_with_history)
        )
        if not should_link:
            continue

        mem = db.scalar(
            select(LibraryMembership).where(
                LibraryMembership.user_id == u.id,
                LibraryMembership.library_id == test_lib.id,
            )
        )
        target_role = (
            MembershipRole.LIBRARY_ADMIN.value
            if is_admin_user
            else MembershipRole.MEMBER.value
        )
        if not mem:
            mem = LibraryMembership(
                user_id=u.id,
                library_id=test_lib.id,
                role=target_role,
                status=MembershipStatus.APPROVED.value,
                department_or_address="Merkez Kütüphane Üyesi",
                application_note="Otomatik Sistem Aktarımı (Test Kütüphanesi)",
            )
            db.add(mem)
        else:
            if is_admin_user and mem.role != MembershipRole.LIBRARY_ADMIN.value:
                mem.role = MembershipRole.LIBRARY_ADMIN.value
            if is_admin_user and mem.status != MembershipStatus.APPROVED.value:
                mem.status = MembershipStatus.APPROVED.value

    db.commit()
    db.refresh(test_lib)
    return test_lib


def _build_library_read(db: Session, lib: Library) -> LibraryRead:
    book_cnt = (
        db.scalar(
            select(func.count()).select_from(Book).where(Book.library_id == lib.id)
        )
        or 0
    )
    member_cnt = (
        db.scalar(
            select(func.count())
            .select_from(LibraryMembership)
            .where(
                LibraryMembership.library_id == lib.id,
                LibraryMembership.status == MembershipStatus.APPROVED.value,
            )
        )
        or 0
    )
    return LibraryRead(
        id=lib.id,
        name=lib.name,
        description=lib.description,
        status=lib.status,
        created_by_id=lib.created_by_id,
        created_by_name=lib.created_by_name,
        created_by_email=lib.created_by_email,
        daily_fine_amount=float(lib.daily_fine_amount or 5.0),
        max_borrow_days=int(lib.max_borrow_days or 14),
        max_books_per_user=int(lib.max_books_per_user or 3),
        penalty_rules_text=lib.penalty_rules_text,
        created_at=lib.created_at,
        book_count=book_cnt,
        member_count=member_cnt,
    )


def _build_membership_read(db: Session, mem: LibraryMembership) -> LibraryMembershipRead:
    today = date.today()
    borrowings = list(
        db.scalars(
            select(Borrowing).where(
                Borrowing.user_id == mem.user_id,
                Borrowing.library_id == mem.library_id,
            )
        ).all()
    )
    active_cnt = 0
    overdue_cnt = 0
    unpaid_total = 0.0
    daily_rate = mem.library_daily_fine_amount

    for b in borrowings:
        due_d = b.due_date.date() if hasattr(b.due_date, "date") else b.due_date
        if b.status != BorrowingStatus.RETURNED and b.approval_status != "PENDING_BORROW":
            active_cnt += 1
            if b.status == BorrowingStatus.OVERDUE or (due_d and today > due_d):
                overdue_cnt += 1
        if not b.is_penalty_paid:
            overdue_days = int(b.overdue_days or 0)
            if (
                b.status != BorrowingStatus.RETURNED
                and b.approval_status != "PENDING_BORROW"
                and due_d
                and today > due_d
                and overdue_days <= 0
            ):
                overdue_days = max(1, (today - due_d).days)
            dmg_pen = float(b.damage_penalty or 0.0)
            calc_pen = round(overdue_days * daily_rate + dmg_pen, 2)
            pen = max(float(b.penalty_amount or 0.0), calc_pen)
            if pen > 0:
                unpaid_total += pen

    return LibraryMembershipRead(
        id=mem.id,
        user_id=mem.user_id,
        user_full_name=mem.user_full_name,
        user_email=mem.user_email,
        library_id=mem.library_id,
        library_name=mem.library_name,
        library_daily_fine_amount=mem.library_daily_fine_amount,
        library_max_borrow_days=mem.library_max_borrow_days,
        library_max_books_per_user=mem.library_max_books_per_user,
        library_penalty_rules_text=mem.library_penalty_rules_text,
        role=mem.role,
        status=mem.status,
        phone=mem.phone,
        identity_or_student_no=mem.identity_or_student_no,
        department_or_address=mem.department_or_address,
        application_note=mem.application_note,
        ban_reason=mem.ban_reason,
        created_at=mem.created_at,
        active_borrowings_count=active_cnt,
        overdue_books_count=overdue_cnt,
        unpaid_penalty_total=round(unpaid_total, 2),
    )


def list_approved_libraries(db: Session, search: str | None = None) -> list[LibraryRead]:
    stmt = select(Library).where(Library.status == LibraryStatus.APPROVED.value)
    if search and search.strip():
        stmt = stmt.where(Library.name.ilike(f"%{search.strip()}%"))
    stmt = stmt.order_by(Library.created_at.asc())
    libs = list(db.scalars(stmt).all())
    return [_build_library_read(db, lib) for lib in libs]


def get_library_detail(db: Session, library_id: uuid.UUID) -> LibraryRead:
    lib = db.get(Library, library_id)
    if not lib:
        raise NotFoundError("Kütüphane bulunamadı")
    return _build_library_read(db, lib)


def get_user_memberships(db: Session, user: User) -> list[LibraryMembershipRead]:
    stmt = (
        select(LibraryMembership)
        .join(Library, Library.id == LibraryMembership.library_id)
        .where(
            LibraryMembership.user_id == user.id,
            Library.status == LibraryStatus.APPROVED.value,
        )
        .order_by(LibraryMembership.created_at.asc())
    )
    memberships = list(db.scalars(stmt).all())
    return [_build_membership_read(db, m) for m in memberships]


def get_user_created_library_requests(db: Session, user: User) -> list[LibraryRead]:
    stmt = (
        select(Library)
        .where(Library.created_by_id == user.id)
        .order_by(Library.created_at.desc())
    )
    libs = list(db.scalars(stmt).all())
    return [_build_library_read(db, lib) for lib in libs]


def create_library_request(
    db: Session, user: User, data: LibraryCreate
) -> LibraryCreateResponse:
    existing = db.scalar(
        select(Library).where(func.lower(Library.name) == data.name.strip().lower())
    )
    if existing:
        raise BusinessRuleError("Bu isimde bir kütüphane veya kütüphane başvurusu zaten mevcut.")

    lib = Library(
        name=data.name.strip(),
        description=data.description,
        status=LibraryStatus.PENDING.value,
        created_by_id=user.id,
        daily_fine_amount=float(data.daily_fine_amount),
        max_borrow_days=int(data.max_borrow_days),
        max_books_per_user=int(data.max_books_per_user),
        penalty_rules_text=data.penalty_rules_text or DEFAULT_PENALTY_RULES_TEXT,
    )
    db.add(lib)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise BusinessRuleError("Bu isimde bir kütüphane zaten mevcut.")
    db.refresh(lib)
    logger.info(
        "Yeni kütüphane kurulum talebi oluşturuldu (PENDING) -> library_id: %s, name: %s, user_id: %s",
        lib.id,
        lib.name,
        user.id,
    )
    return LibraryCreateResponse(
        message=LIBRARY_CREATE_PENDING_MESSAGE,
        library=_build_library_read(db, lib),
    )


def list_all_libraries_for_system_admin(
    db: Session, actor: User, status_filter: str | None = None
) -> list[LibraryRead]:
    require_system_admin_access(actor)
    stmt = select(Library)
    if status_filter and status_filter.upper() != "ALL":
        stmt = stmt.where(Library.status == status_filter.upper())
    stmt = stmt.order_by(Library.created_at.desc())
    libs = list(db.scalars(stmt).all())
    return [_build_library_read(db, lib) for lib in libs]


def update_library_status_by_system_admin(
    db: Session, actor: User, library_id: uuid.UUID, status_str: str
) -> LibraryRead:
    require_system_admin_access(actor)
    lib = db.get(Library, library_id)
    if not lib:
        raise NotFoundError("Kütüphane bulunamadı")

    new_status = status_str.upper()
    if new_status not in (LibraryStatus.APPROVED.value, LibraryStatus.REJECTED.value):
        raise BusinessRuleError("Geçersiz kütüphane durumu (APPROVED veya REJECTED olmalıdır).")

    lib.status = new_status
    if new_status == LibraryStatus.APPROVED.value and lib.created_by_id:
        creator = db.get(User, lib.created_by_id)
        if creator:
            role_lib_admin = _ensure_role(db, RoleName.LIBRARY_ADMIN)
            if not creator.has_role(RoleName.LIBRARY_ADMIN):
                creator.roles.append(role_lib_admin)

            mem = db.scalar(
                select(LibraryMembership).where(
                    LibraryMembership.user_id == creator.id,
                    LibraryMembership.library_id == lib.id,
                )
            )
            if not mem:
                mem = LibraryMembership(
                    user_id=creator.id,
                    library_id=lib.id,
                    role=MembershipRole.LIBRARY_ADMIN.value,
                    status=MembershipStatus.APPROVED.value,
                    application_note="Kütüphane Kurucusu ve Yöneticisi (Sistem Yöneticisi Onaylı)",
                )
                db.add(mem)
            else:
                mem.role = MembershipRole.LIBRARY_ADMIN.value
                mem.status = MembershipStatus.APPROVED.value

    db.commit()
    db.refresh(lib)
    logger.info(
        "Sistem Yöneticisi kütüphane durumunu güncelledi -> library_id: %s, name: %s, status: %s, admin: %s",
        lib.id,
        lib.name,
        lib.status,
        actor.email,
    )
    return _build_library_read(db, lib)


def apply_to_library(
    db: Session, user: User, data: LibraryMembershipApplyRequest
) -> LibraryMembershipRead:
    lib: Library | None = None
    if data.library_id:
        lib = db.get(Library, data.library_id)
    elif data.library_name and data.library_name.strip():
        clean_name = data.library_name.strip()
        lib = db.scalar(
            select(Library).where(
                func.lower(Library.name) == clean_name.lower(),
                Library.status == LibraryStatus.APPROVED.value,
            )
        )
        if not lib:
            lib = db.scalar(
                select(Library).where(
                    Library.name.ilike(f"%{clean_name}%"),
                    Library.status == LibraryStatus.APPROVED.value,
                )
            )

    if not lib or lib.status != LibraryStatus.APPROVED.value:
        raise NotFoundError(
            "Belirtilen isimde onaylı bir kütüphane bulunamadı. Lütfen kütüphane adını kontrol ediniz."
        )

    existing = db.scalar(
        select(LibraryMembership).where(
            LibraryMembership.user_id == user.id,
            LibraryMembership.library_id == lib.id,
        )
    )
    if existing:
        if existing.status == MembershipStatus.BANNED.value:
            raise BusinessRuleError(
                f"'{lib.name}' kütüphanesindeki üyeliğiniz yönetici tarafından kısıtlanmıştır (Banlı). "
                f"Sebep: {existing.ban_reason or 'Kütüphane kuralları ihlali'}"
            )
        if existing.status == MembershipStatus.APPROVED.value:
            raise BusinessRuleError(f"'{lib.name}' kütüphanesine zaten onaylı üyesiniz.")
        if existing.status == MembershipStatus.PENDING.value:
            raise BusinessRuleError(
                f"'{lib.name}' kütüphanesi için zaten yönetici onayı bekleyen bir başvurunuz bulunmaktadır."
            )
        # REJECTED ise tekrar başvurabilsin
        existing.status = MembershipStatus.PENDING.value
        existing.phone = data.phone.strip()
        existing.identity_or_student_no = data.identity_or_student_no.strip()
        existing.department_or_address = data.department_or_address.strip()
        existing.application_note = (data.application_note or "").strip() or None
        db.commit()
        db.refresh(existing)
        return _build_membership_read(db, existing)

    mem = LibraryMembership(
        user_id=user.id,
        library_id=lib.id,
        role=MembershipRole.MEMBER.value,
        status=MembershipStatus.PENDING.value,
        phone=data.phone.strip(),
        identity_or_student_no=data.identity_or_student_no.strip(),
        department_or_address=data.department_or_address.strip(),
        application_note=(data.application_note or "").strip() or None,
    )
    db.add(mem)
    db.commit()
    db.refresh(mem)
    logger.info(
        "Kullanıcı kütüphaneye üyelik başvurusu yaptı (PENDING) -> user_id: %s, library: %s",
        user.id,
        lib.name,
    )
    return _build_membership_read(db, mem)


def update_library_settings(
    db: Session, actor: User, library_id: uuid.UUID, data: LibrarySettingsUpdate
) -> LibraryRead:
    lib = require_library_admin_access(db, actor, library_id)
    update_fields = data.model_dump(exclude_unset=True)
    if "name" in update_fields and update_fields["name"]:
        new_name = update_fields["name"].strip()
        dup = db.scalar(
            select(Library).where(
                func.lower(Library.name) == new_name.lower(),
                Library.id != lib.id,
            )
        )
        if dup:
            raise BusinessRuleError("Bu kütüphane adı başka bir kütüphane tarafından kullanılıyor.")
        lib.name = new_name

    if "description" in update_fields:
        lib.description = update_fields["description"]
    if "daily_fine_amount" in update_fields and update_fields["daily_fine_amount"] is not None:
        lib.daily_fine_amount = float(update_fields["daily_fine_amount"])
    if "max_borrow_days" in update_fields and update_fields["max_borrow_days"] is not None:
        lib.max_borrow_days = int(update_fields["max_borrow_days"])
    if "max_books_per_user" in update_fields and update_fields["max_books_per_user"] is not None:
        lib.max_books_per_user = int(update_fields["max_books_per_user"])
    if "penalty_rules_text" in update_fields:
        lib.penalty_rules_text = update_fields["penalty_rules_text"]

    db.commit()
    db.refresh(lib)
    logger.info(
        "Kütüphane ve ceza ayarları güncellendi -> library_id: %s, daily_fine: %.2f, max_days: %d, max_books: %d",
        lib.id,
        lib.daily_fine_amount,
        lib.max_borrow_days,
        lib.max_books_per_user,
    )
    return _build_library_read(db, lib)


def list_library_members(
    db: Session, actor: User, library_id: uuid.UUID, status_filter: str | None = None
) -> list[LibraryMembershipRead]:
    require_library_admin_access(db, actor, library_id)
    stmt = select(LibraryMembership).where(LibraryMembership.library_id == library_id)
    if status_filter and status_filter.upper() != "ALL":
        stmt = stmt.where(LibraryMembership.status == status_filter.upper())
    stmt = stmt.order_by(LibraryMembership.created_at.desc())
    members = list(db.scalars(stmt).all())
    return [_build_membership_read(db, m) for m in members]


def update_membership_status(
    db: Session,
    actor: User,
    library_id: uuid.UUID,
    membership_id: uuid.UUID,
    data: LibraryMembershipStatusUpdate,
) -> LibraryMembershipRead:
    require_library_admin_access(db, actor, library_id)
    mem = db.get(LibraryMembership, membership_id)
    if not mem or mem.library_id != library_id:
        raise NotFoundError("Üyelik kaydı bu kütüphanede bulunamadı")

    new_st = data.status.upper()
    if mem.user_id == actor.id and new_st in (
        MembershipStatus.BANNED.value,
        MembershipStatus.REJECTED.value,
    ):
        raise BusinessRuleError("Kendi kütüphane üyeliğinizi banlayamaz veya reddedemezsiniz.")

    if mem.user and is_user_system_admin(mem.user) and new_st == MembershipStatus.BANNED.value:
        raise BusinessRuleError("Sistem Yöneticisi (SYSTEM_ADMIN) hesabını banlayamazsınız.")

    mem.status = new_st
    if new_st == MembershipStatus.BANNED.value:
        mem.ban_reason = (data.ban_reason or "").strip() or (
            "Kütüphane kuralları gereğince bu kütüphanedeki üyeliğiniz ve katalog erişiminiz kısıtlanmıştır."
        )
    elif new_st == MembershipStatus.APPROVED.value:
        mem.ban_reason = None

    db.commit()
    db.refresh(mem)
    logger.info(
        "Kütüphane üyelik durumu güncellendi -> library_id: %s, membership_id: %s, status: %s, actor: %s",
        library_id,
        mem.id,
        mem.status,
        actor.email,
    )
    return _build_membership_read(db, mem)


def update_membership_role(
    db: Session,
    actor: User,
    library_id: uuid.UUID,
    membership_id: uuid.UUID,
    data: LibraryMembershipRoleUpdate,
) -> LibraryMembershipRead:
    require_library_admin_access(db, actor, library_id)
    mem = db.get(LibraryMembership, membership_id)
    if not mem or mem.library_id != library_id:
        raise NotFoundError("Üyelik kaydı bu kütüphanede bulunamadı")

    if not data.confirmed:
        raise BusinessRuleError("Yönetici yetkisi ataması için onay uyarısının kabul edilmesi zorunludur.")

    if mem.status != MembershipStatus.APPROVED.value:
        raise BusinessRuleError(
            "Yalnızca onaylı (APPROVED) kütüphane üyelerine yönetici yetkisi verilebilir."
        )

    new_role = data.role.upper()
    mem.role = new_role
    if new_role == MembershipRole.LIBRARY_ADMIN.value and mem.user:
        role_lib_admin = _ensure_role(db, RoleName.LIBRARY_ADMIN)
        if not mem.user.has_role(RoleName.LIBRARY_ADMIN):
            mem.user.roles.append(role_lib_admin)

    db.commit()
    db.refresh(mem)
    logger.info(
        "Kütüphane üyelik yetkisi güncellendi -> library_id: %s, target_user: %s, role: %s, actor: %s",
        library_id,
        mem.user_email,
        mem.role,
        actor.email,
    )
    return _build_membership_read(db, mem)

