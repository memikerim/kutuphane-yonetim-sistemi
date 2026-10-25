from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine_kwargs = {"pool_pre_ping": True}
if not settings.DATABASE_URL.startswith("sqlite"):
    engine_kwargs.update({
        "pool_size": 5,
        "max_overflow": 2,
        "pool_recycle": 300,
    })

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: her istek için bir DB oturumu açar ve kapatır."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Endpoint imzalarında kısa kullanım için: def endpoint(db: DbSession): ...
DbSession = Annotated[Session, Depends(get_db)]

