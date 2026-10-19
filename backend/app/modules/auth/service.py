"""Auth iş mantığı. HTTP'den bağımsızdır; hatalar domain exception olarak fırlatılır."""

import logging
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    hash_password,
    verify_dummy_password,
    verify_password,
)
from app.modules.auth.models import Role, RoleName, User
from app.modules.auth.schemas import TokenResponse, UserRegister

logger = logging.getLogger(__name__)


class EmailAlreadyRegisteredError(Exception):
    """Kayıt sırasında e-posta zaten kullanılıyorsa fırlatılır."""


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))


def get_or_create_role(db: Session, name: RoleName) -> Role:
    role = db.scalar(select(Role).where(Role.name == name))
    if role is None:  # Seed migration çalışmamışsa bile sistem çalışmaya devam etsin
        role = Role(name=name)
        db.add(role)
        db.flush()
    return role


def register_user(db: Session, data: UserRegister) -> User:
    if get_user_by_email(db, data.email) is not None:
        logger.warning("Kullanıcı kaydı başarısız: E-posta zaten kayıtlı -> %s", data.email)
        raise EmailAlreadyRegisteredError

    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        first_name=data.first_name,
        last_name=data.last_name,
        roles=[get_or_create_role(db, RoleName.USER)],  # varsayılan rol
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        # Aynı anda gelen iki kayıt isteğinde unique constraint son savunma hattıdır
        db.rollback()
        logger.warning("Kullanıcı kaydı çakışması (race condition) -> %s", data.email)
        raise EmailAlreadyRegisteredError from exc
    db.refresh(user)
    logger.info("Yeni kullanıcı başarıyla kaydedildi -> email: %s, user_id: %s", user.email, user.id)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """Bilgiler doğruysa kullanıcıyı, değilse None döner."""
    user = get_user_by_email(db, email)
    if user is None:
        verify_dummy_password(password)
        logger.warning("Başarısız giriş denemesi: Kullanıcı bulunamadı -> email: %s", email)
        return None
    if not verify_password(password, user.password_hash):
        logger.warning("Başarısız giriş denemesi: Hatalı şifre -> email: %s", email)
        return None
    logger.info("Kullanıcı kimlik doğrulaması başarılı -> email: %s, user_id: %s", user.email, user.id)
    return user


def issue_access_token(user: User) -> TokenResponse:
    token = create_access_token(
        user_id=user.id,
        email=user.email,
        roles=[role.name.value for role in user.roles],
    )
    logger.info("Kullanıcı için access token üretildi -> user_id: %s, email: %s", user.id, user.email)
    return TokenResponse(
        access_token=token, expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
