from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from pydantic import BaseModel
import os

base_dir = Path.cwd()

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.path.join(base_dir, ".env"),
        env_ignore_empty=True,
    )

    database_url: str = "sqlite:///./curu.db"
    jwt_secret: str
    frontend_url: str = "http://localhost:5173"
    bot_token: str = ""
    bot_username: str = ""
    support_chat_id: int | None = None
    seed_demo: bool = False
    admin_email: str = "demo@curu.local"
    admin_password: str = ""
    mistral_api_key: str = ""

class Config(BaseModel):
    categories: list[str] = ["Одежда", "Гаджеты", "Книги", "Для учёбы", "Для дома", "Другое"]

config = Config()
settings = Settings()
