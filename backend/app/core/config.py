from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Hem backend/ hem de proje kökünden çalıştırmayı destekler
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "Kutuphane Yonetim Sistemi"
    APP_ENV: str = "development"
    PORT: int = 8000

    # Bulut veritabanı doğrudan DATABASE_URL verebilir (Neon.tech, Supabase vb.)
    DATABASE_URL_ENV: str | None = Field(default=None, alias="DATABASE_URL")

    # Yerel geliştirme ve docker-compose için varsayılan değişkenler
    DB_USER: str = "library_user"
    DB_PASSWORD: str = "library_pass_2026"
    DB_NAME: str = "library_db"
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432

    JWT_SECRET: str = "DAnNssLn4UnueaMFsKpnJrVDUKdDX4ehwpQAJXKPPIjq2vkfXNo6T-7kIu-5-OFM"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    DAILY_PENALTY_RATE: float = 10.0

    @property
    def DATABASE_URL(self) -> str:
        url = self.DATABASE_URL_ENV
        if not url:
            url = (
                f"postgresql+psycopg://{self.DB_USER}:{self.DB_PASSWORD}"
                f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            )
        # Heroku / Neon / Supabase 'postgres://' verirse SQLAlchemy için 'postgresql://' olarak düzeltir
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://") :]
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
