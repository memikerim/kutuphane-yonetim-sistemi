import uuid
from collections.abc import Generator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # Tüm modelleri ve ilişkileri yükler
from app.core.base_model import Base
from app.core.database import get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.modules.auth.models import Role, RoleName, User
from app.modules.catalog.models import Author, Book, Category, Publisher

# Testler için izole in-memory SQLite veritabanı (StaticPool ile tek bellek alanı)
TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """Her test fonksiyonu için temiz bir veritabanı şeması ve oturumu sağlar."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    
    # Varsayılan rolleri oluştur
    user_role = Role(name=RoleName.USER)
    admin_role = Role(name=RoleName.ADMIN)
    session.add_all([user_role, admin_role])
    session.commit()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """get_db bağımlılığı test oturumuna yönlendirilmiş TestClient."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db_session: Session) -> User:
    """USER rolüne sahip örnek kullanıcı."""
    user_role = db_session.query(Role).filter_by(name=RoleName.USER).first()
    user = User(
        email="testuser@example.com",
        password_hash=hash_password("password123"),
        first_name="Test",
        last_name="User",
        roles=[user_role],
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def user_token(test_user: User) -> str:
    """Test kullanıcısı için geçerli JWT token."""
    return create_access_token(
        user_id=test_user.id,
        email=test_user.email,
        roles=["USER"],
    )


@pytest.fixture
def auth_headers(user_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_token}"}


@pytest.fixture
def admin_user(db_session: Session) -> User:
    """ADMIN rolüne sahip örnek kullanıcı."""
    admin_role = db_session.query(Role).filter_by(name=RoleName.ADMIN).first()
    user = User(
        email="admin@example.com",
        password_hash=hash_password("adminpass123"),
        first_name="Admin",
        last_name="User",
        roles=[admin_role],
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_token(admin_user: User) -> str:
    """Admin kullanıcısı için geçerli JWT token."""
    return create_access_token(
        user_id=admin_user.id,
        email=admin_user.email,
        roles=["ADMIN"],
    )


@pytest.fixture
def admin_headers(admin_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def test_book(db_session: Session) -> Book:
    """Örnek yazar, kategori, yayınevi ve 5 stoklu kitap."""
    author = Author(first_name="Fyodor", last_name="Dostoyevski")
    category = Category(name="Klasik")
    publisher = Publisher(name="İletişim Yayınları", contact_info="info@iletisim.com.tr")
    db_session.add_all([author, category, publisher])
    db_session.commit()

    book = Book(
        title="Suç ve Ceza",
        isbn="9789750500001",
        published_year=1866,
        stock_count=5,
        publisher_id=publisher.id,
        authors=[author],
        categories=[category],
    )
    db_session.add(book)
    db_session.commit()
    db_session.refresh(book)
    return book

