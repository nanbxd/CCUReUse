from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from collections.abc import Iterator
from config import config, settings

engine = create_engine(settings.database_url, connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)

def get_db() -> Iterator[Session]:
    with SessionLocal() as db:
        yield db
