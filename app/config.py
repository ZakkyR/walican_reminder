from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./test.db"
    discord_client_id: str = ""
    discord_client_secret: str = ""
    discord_bot_token: str = ""
    discord_redirect_uri: str = "http://localhost:8000/auth/callback"
    session_secret: str = "dev-secret-change-in-production"
    internal_notify_key: str = ""
    app_base_url: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def sqlalchemy_url(self) -> str:
        return self.database_url


settings = Settings()
