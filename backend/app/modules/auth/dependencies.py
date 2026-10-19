"""Yetkilendirme dependency'leri (guard'lar).

Kullanım:
    @router.get("/me")
    def me(user: CurrentUser): ...

    @router.get("/admin/x", dependencies=[Depends(require_roles(["ADMIN"]))])
    def x(): ...
"""

import uuid
from collections.abc import Callable, Iterable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from app.core.database import DbSession
from app.core.security import decode_access_token
from app.modules.auth.models import RoleName, User

# auto_error=False: header yoksa FastAPI'nin varsayılan 403'ü yerine kendimiz 401 döneriz
bearer_scheme = HTTPBearer(
    auto_error=False,
    description="POST /api/v1/auth/login ile alınan access_token değerini yapıştırın.",
)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: DbSession,
) -> User:
    """`Authorization: Bearer <token>` header'ını doğrular ve kullanıcıyı DB'den yükler."""
    if credentials is None:
        raise _unauthorized("Kimlik doğrulama gerekli")

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = uuid.UUID(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise _unauthorized("Geçersiz veya süresi dolmuş token") from None

    user = db.get(User, user_id)
    if user is None:  # token geçerli ama kullanıcı silinmiş
        raise _unauthorized("Kullanıcı bulunamadı")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(allowed_roles: Iterable[RoleName | str]) -> Callable[[User], User]:
    """Kullanıcının izin verilen rollerden EN AZ BİRİNE sahip olmasını şart koşar.

    Roller token'dan değil DB'den okunur; böylece bir rol geri alındığında
    eski token'lar o yetkiyi kullanmaya devam edemez.
    """
    allowed = {RoleName(role) for role in allowed_roles}  # geçersiz rol adı -> açılışta hata

    def role_checker(user: CurrentUser) -> User:
        user_roles = {role.name for role in user.roles}
        if user_roles.isdisjoint(allowed):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bu işlem için yetkiniz yok",
            )
        return user

    return role_checker

