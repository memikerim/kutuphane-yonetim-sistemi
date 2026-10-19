import pytest
from jose import jwt

from app.core.config import settings
from app.core.security import hash_password, verify_dummy_password, verify_password
from app.modules.auth import service
from app.modules.auth.models import RoleName
from app.modules.auth.schemas import UserRegister


def test_hash_and_verify_password():
    raw = "guclu_sifre_123"
    hashed = hash_password(raw)
    assert hashed != raw
    assert verify_password(raw, hashed) is True
    assert verify_password("yanlis_sifre", hashed) is False


def test_verify_dummy_password():
    # Zamanlama saldırılarını önlemek için dummy doğrulama çağrılabilir ve patlamaz
    verify_dummy_password("herhangi_bir_sifre")


def test_register_user_success(db_session):
    data = UserRegister(
        email="yeni@example.com",
        password="password123",
        first_name="Ahmet",
        last_name="Yılmaz",
    )
    user = service.register_user(db_session, data)
    assert user.id is not None
    assert user.email == "yeni@example.com"
    assert verify_password("password123", user.password_hash) is True
    assert len(user.roles) == 1
    assert user.roles[0].name == RoleName.USER


def test_register_user_duplicate_email(db_session):
    data = UserRegister(
        email="ayni@example.com",
        password="password123",
        first_name="Ali",
        last_name="Kaya",
    )
    service.register_user(db_session, data)

    with pytest.raises(service.EmailAlreadyRegisteredError):
        service.register_user(db_session, data)


def test_authenticate_user_success(db_session):
    data = UserRegister(
        email="auth_test@example.com",
        password="mypassword123",
        first_name="Can",
        last_name="Demir",
    )
    service.register_user(db_session, data)

    user = service.authenticate_user(db_session, "auth_test@example.com", "mypassword123")
    assert user is not None
    assert user.email == "auth_test@example.com"


def test_authenticate_user_invalid_password(db_session):
    data = UserRegister(
        email="auth_invalid@example.com",
        password="mypassword123",
        first_name="Can",
        last_name="Demir",
    )
    service.register_user(db_session, data)

    user = service.authenticate_user(db_session, "auth_invalid@example.com", "wrong_password")
    assert user is None


def test_authenticate_user_not_found(db_session):
    user = service.authenticate_user(db_session, "olmayan@example.com", "password")
    assert user is None


def test_issue_access_token(db_session):
    data = UserRegister(
        email="token_test@example.com",
        password="password123",
        first_name="Token",
        last_name="User",
    )
    user = service.register_user(db_session, data)
    token_resp = service.issue_access_token(user)

    assert token_resp.access_token is not None
    assert token_resp.token_type == "bearer"
    assert token_resp.expires_in > 0

    payload = jwt.decode(
        token_resp.access_token,
        settings.JWT_SECRET,
        algorithms=[settings.JWT_ALGORITHM],
    )
    assert payload["sub"] == str(user.id)
    assert payload["email"] == user.email
    assert "USER" in payload["roles"]

