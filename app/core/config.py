from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    secret_key: str = "dev-secret-change-me"
    database_url: str = "sqlite+aiosqlite:///./data/hub.db"
    access_token_expire_minutes: int = 12 * 60

    device_api_key: str = "your-secret-api-key-change-this"
    device_http_port: int = 80

    scan_cidr: str | None = None
    scan_interval_seconds: int = 300
    poll_interval_seconds: int = 10

    admin_username: str = "admin"
    admin_password: str = "admin"


settings = Settings()