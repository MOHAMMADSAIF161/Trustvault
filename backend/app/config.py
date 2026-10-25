from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    postgres_password: str | None = None
    postgres_runtime_password: str | None = None

    master_encryption_key: str
    jwt_secret: str

    database_url: str | None = None
    access_token_expire_minutes: int = 10
    redis_url: str = "redis://127.0.0.1:6379/0"
    database_name: str = "trustvault_test"

    model_config = SettingsConfigDict(
        env_file="../.env",
        extra="ignore",
    )


settings = Settings()


if settings.database_url:
    url = settings.database_url

    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]

    if url.startswith("postgresql://"):
        url = url.replace(
            "postgresql://",
            "postgresql+psycopg://",
            1,
        )

    DATABASE_URL = url

else:
    if not settings.postgres_runtime_password:
        raise ValueError(
            "Set DATABASE_URL or POSTGRES_RUNTIME_PASSWORD."
        )

    DATABASE_URL = (
        "postgresql+psycopg://trustvault_runtime:"
        f"{settings.postgres_runtime_password}"
        f"@127.0.0.1:5433/{settings.database_name}"
    )