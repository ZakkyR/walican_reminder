from urllib.parse import quote_plus
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./test.db"
    discord_client_id: str = ""
    discord_client_secret: str = ""
    discord_bot_token: str = ""
    discord_redirect_uri: str = "http://localhost:8000/auth/callback"
    session_secret: str = "dev-secret-change-in-production"
    functions_url: str = ""
    functions_key: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def sqlalchemy_url(self) -> str:
        # Azure Portal からコピーした生の ODBC 文字列をそのまま DATABASE_URL に設定できるよう変換する。
        # 例: "Driver={ODBC Driver 18 for SQL Server};Server=tcp:...;Pwd=P@ss;..."
        # → "mssql+pyodbc:///?odbc_connect=Driver%3D..."
        if self.database_url.startswith("Driver="):
            return f"mssql+pyodbc:///?odbc_connect={quote_plus(self.database_url)}"
        return self.database_url


settings = Settings()
