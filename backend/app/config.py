
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    postgres_password: str
    postgres_runtime_password: str
    master_encryption_key: str
    jwt_secret: str
    access_token_expire_minutes: int = 10
    redis_url: str = "redis://127.0.0.1:6379/0"
    database_name: str = "trustvault_test"

    model_config = SettingsConfigDict(
        env_file="../.env",
        extra="ignore",
    )


settings = Settings()

DATABASE_URL = (
    "postgresql+psycopg://trustvault_runtime:"
    f"{settings.postgres_runtime_password}"
    f"@127.0.0.1:5433/{settings.database_name}"
)
