from fastapi import APIRouter, HTTPException, status

from app.core.database import DbSession
from app.modules.auth import service
from app.modules.auth.dependencies import CurrentUser
from app.modules.auth.schemas import TokenResponse, UserLogin, UserRead, UserRegister

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Yeni kullanıcı kaydı (varsayılan rol: USER)",
    responses={400: {"description": "E-posta zaten kayıtlı"}},
)
def register(data: UserRegister, db: DbSession):
    try:
        return service.register_user(db, data)
    except service.EmailAlreadyRegisteredError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu e-posta adresi zaten kayıtlı",
        ) from None


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="E-posta ve şifre ile giriş, JWT access token döner",
    responses={401: {"description": "E-posta veya şifre hatalı"}},
)
def login(data: UserLogin, db: DbSession):
    user = service.authenticate_user(db, data.email, data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-posta veya şifre hatalı",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return service.issue_access_token(user)


@router.get(
    "/me",
    response_model=UserRead,
    summary="Giriş yapmış kullanıcının bilgileri (token gerekli)",
    responses={401: {"description": "Token yok / geçersiz"}},
)
def me(current_user: CurrentUser, db: DbSession):
    return service.build_user_read_with_alerts(db, current_user)
