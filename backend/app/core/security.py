"""Şifre hashleme ve JWT yardımcıları.

Bu modül framework'ten bağımsızdır (FastAPI import etmez); HTTP'ye özgü
hata yönetimi auth modülündeki dependency'lerde yapılır.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# ---------------------------------------------------------------------------
# Şifre güvenliği (bcrypt)
# ---------------------------------------------------------------------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Düz metin şifreyi bcrypt ile (rastgele salt'lı) hashler."""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Düz metin şifrenin verilen hash ile eşleşip eşleşmediğini kontrol eder."""
    return pwd_context.verify(plain_password, password_hash)


# Kullanıcı bulunamadığında da bir bcrypt doğrulaması yaparak yanıt süresini eşitler;
# böylece "bu e-posta kayıtlı mı?" bilgisinin zamanlama farkından sızması engellenir.
_DUMMY_HASH = hash_password("timing-attack-dummy-password")


def verify_dummy_password(plain_password: str) -> None:
    pwd_context.verify(plain_password, _DUMMY_HASH)


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------
TOKEN_TYPE_ACCESS = "access"


def create_access_token(
    *,
    user_id: uuid.UUID,
    email: str,
    roles: list[str],
    expires_delta: timedelta | None = None,
) -> str:
    """sub (kullanıcı id), email ve roles claim'lerini içeren imzalı bir access token üretir."""
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "roles": roles,
        "type": TOKEN_TYPE_ACCESS,
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Token'ı doğrular ve payload'ı döner.

    İmza geçersizse, süresi dolmuşsa veya access token değilse ``JWTError`` fırlatır.
    """
    # algorithms parametresi açıkça verilerek "algorithm confusion" saldırıları engellenir
    payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    if payload.get("type") != TOKEN_TYPE_ACCESS or not payload.get("sub"):
        raise JWTError("Geçersiz token tipi")
    return payload

