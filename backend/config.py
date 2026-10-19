from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from pydantic import BaseModel, Field
import os
from sqlalchemy.engine import URL

base_dir = Path.cwd()

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.path.join(base_dir, ".env"), extra="ignore"
    )

    database_url_override: str = Field(default="", validation_alias="DATABASE_URL")
    db_user: str = ""
    db_password: str = ""
    db_port: int = 5432
    db_host: str = "localhost"
    db_name: str = "curu"

    jwt_secret: str
    frontend_url: str = "http://localhost:5173"
    bot_token: str = ""
    bot_username: str = ""
    support_chat_id: int | None = None
    seed_demo: bool = False
    admin_email: str = "demo@curu.local"
    admin_password: str = ""
    mistral_api_key: str = ""
    agnes_api_key: str = ""

    @property
    def database_url(self) -> str:
        if self.database_url_override:
            url = self.database_url_override
            if url.startswith("postgres://"):
                url = "postgresql+psycopg://" + url[len("postgres://"):]
            elif url.startswith("postgresql://"):
                url = "postgresql+psycopg://" + url[len("postgresql://"):]
            return url
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        ).render_as_string(hide_password=False)

class Config(BaseModel):
    categories: list[str] = ["Одежда", "Гаджеты", "Книги", "Для учёбы", "Для дома", "Другое"]

config = Config()
settings = Settings()