import asyncio, base64, hashlib, hmac, os, secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Annotated
import jwt
from aiogram import Bot
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, inspect, or_, select, text
from sqlalchemy.orm import Session
from config import config, settings
from database.models import *
from database.db import get_db, engine, SessionLocal
from bot import run_bot
from models import UserIn, ProfileIn, LoginIn, ListingIn, StatusIn, PreferencesIn


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310000)
    return f"{base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, expected = stored.split("$", 1)
        actual = hash_password(password, base64.b64decode(salt)).split("$", 1)[1]
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def token_for(user_id: int, purpose: str = "access", minutes: int = 60 * 24 * 14) -> str:
    return jwt.encode({"sub": str(user_id), "purpose": purpose, "exp": datetime.now(timezone.utc) + timedelta(minutes=minutes)}, settings.jwt_secret, algorithm="HS256")


def telegram_code(user_id: int) -> str:
    payload = f"{user_id:x}.{int((datetime.now(timezone.utc) + timedelta(minutes=15)).timestamp()):x}"
    signature = hmac.new(settings.jwt_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()[:20]
    return f"{payload}.{signature}"


bearer = HTTPBearer(auto_error=False)


def current_user(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)], db: Annotated[Session, Depends(get_db)]) -> User:
    if not credentials:
        raise HTTPException(401, "Войдите в аккаунт")
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=["HS256"])
        if payload.get("purpose") != "access":
            raise ValueError()
        user = db.get(User, int(payload["sub"]))
        if user:
            return user
    except (jwt.PyJWTError, ValueError, KeyError):
        pass
    raise HTTPException(401, "Сессия истекла. Войдите снова")


def user_data(user: User) -> dict:
    return {"id": user.id, "name": user.name, "email": user.email, "education_level": user.education_level, "study_group": user.study_group, "contact": user.contact, "bio": user.bio, "is_admin": user.is_admin, "created_at": user.created_at.isoformat()}


def migrate_user_columns():
    # create_all does not add columns to existing installations.
    if inspect(engine).has_table("users"):
        columns = {column["name"] for column in inspect(engine).get_columns("users")}
        with engine.begin() as connection:
            if "is_admin" not in columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT FALSE"))
            if "education_level" not in columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN education_level VARCHAR(20) NOT NULL DEFAULT ''"))
            if "study_group" not in columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN study_group VARCHAR(40) NOT NULL DEFAULT ''"))


def prepare_admin():
    if not settings.admin_password:
        return
    if len(settings.admin_password) < 12:
        raise RuntimeError("ADMIN_PASSWORD must be at least 12 characters")
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == settings.admin_email))
        if not user:
            user = User(name="Команда CURU", email=settings.admin_email, faculty="Caspian University", contact="", bio="Команда CURU")
            db.add(user)
        user.password_hash = hash_password(settings.admin_password)
        user.is_admin = True
        db.commit()


def listing_data(item: Listing) -> dict:
    return {
        "id": item.id,
        "title": item.title,
        "description": item.description,
        "category": item.category,
        "condition": item.condition,
        "location": item.location,
        "image": item.image,
        "status": item.status,
        "created_at": item.created_at.isoformat(),
        "owner": user_data(item.owner),
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    migrate_user_columns()
    if os.getenv("SEED_DEMO", "true").lower() == "true":
        seed_demo()
    prepare_admin()
    task = asyncio.create_task(run_bot()) if settings.bot_token else None
    yield
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="CURU API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[v.strip() for v in os.getenv("FRONTEND_URL", "http://localhost:5173").split(",")], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/categories")
def categories():
    return config.categories


@app.get("/api/support")
def support_info():
    return {
        "bot_url": f"https://t.me/{settings.bot_username}?start=support"
        if settings.bot_username and settings.bot_token and settings.support_chat_id
        else ""
    }


@app.post("/api/auth/register", status_code=201)
def register(data: UserIn, db: Annotated[Session, Depends(get_db)]):
    email = data.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "Этот email уже зарегистрирован")
    user = User(name=data.name.strip(), email=email, password_hash=hash_password(data.password), education_level=data.education_level, study_group=data.study_group.strip(), contact=data.contact.strip())
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"token": token_for(user.id), "user": user_data(user)}


@app.post("/api/auth/login")
def login(data: LoginIn, db: Annotated[Session, Depends(get_db)]):
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Неверный email или пароль")
    return {"token": token_for(user.id), "user": user_data(user)}


@app.get("/api/me")
def me(user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]):
    mine = db.scalars(select(Listing).where(Listing.owner_id == user.id).order_by(Listing.created_at.desc())).all()
    return {**user_data(user), "listings": [listing_data(item) for item in mine], "stats": {"published": len(mine), "given": sum(item.status == "given" for item in mine), "active": sum(item.status != "given" for item in mine)}}


@app.patch("/api/me")
def update_me(data: ProfileIn, user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]):
    for key, value in data.model_dump().items():
        if value is not None:
            setattr(user, key, value.strip())
    db.commit()
    return user_data(user)


@app.get("/api/users/{user_id}")
def public_user(user_id: int, db: Annotated[Session, Depends(get_db)]):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "Студент не найден")
    items = db.scalars(select(Listing).where(Listing.owner_id == user_id).order_by(Listing.created_at.desc())).all()
    return {**user_data(user), "listings": [listing_data(item) for item in items], "stats": {"published": len(items), "given": sum(item.status == "given" for item in items)}}


@app.get("/api/listings")
def listings(db: Annotated[Session, Depends(get_db)], category: str | None = None, q: str | None = None, status: str = "available", limit: int = Query(60, ge=1, le=100), offset: int = Query(0, ge=0)):
    stmt = select(Listing).order_by(Listing.created_at.desc(), Listing.id.desc())
    if category and category != "Все":
        stmt = stmt.where(Listing.category == category)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(or_(Listing.title.ilike(pattern), Listing.description.ilike(pattern)))
    if status != "all":
        stmt = stmt.where(Listing.status == status)
    return [listing_data(item) for item in db.scalars(stmt.offset(offset).limit(limit)).all()]


@app.get("/api/listings/{listing_id}")
def listing(listing_id: int, db: Annotated[Session, Depends(get_db)]):
    item = db.get(Listing, listing_id)
    if not item:
        raise HTTPException(404, "Вещь не найдена")
    return listing_data(item)


async def notify_subscribers(listing_id: int):
    if not settings.bot_token:
        return
    with SessionLocal() as db:
        item = db.get(Listing, listing_id)
        if not item:
            return
        subs = db.scalars(select(Subscription).where(Subscription.enabled == True, Subscription.user_id != item.owner_id)).all()
        telegram_subs = db.scalars(select(TelegramSubscription).where(TelegramSubscription.enabled == True)).all()
        recipients = sorted({s.chat_id for s in [*subs, *telegram_subs] if item.category in s.categories.split("|")})
        title, category, location = item.title, item.category, item.location
    bot = Bot(settings.bot_token)
    frontend = os.getenv("FRONTEND_URL", "http://localhost:5173").split(",")[0].strip().rstrip("/")
    try:
        for chat_id in recipients:
            try:
                await bot.send_message(chat_id, f"♻️ Новая вещь на CURU!\n\n{title}\n{category} · {location}\n\n{frontend}/listing/{listing_id}")
            except Exception:
                pass
    finally:
        await bot.session.close()


@app.post("/api/listings", status_code=201)
def create_listing(data: ListingIn, tasks: BackgroundTasks, user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]):
    if not user.contact.strip():
        raise HTTPException(400, "Сначала добавьте контакт для связи в профиле")
    item = Listing(**data.model_dump(), owner_id=user.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    tasks.add_task(notify_subscribers, item.id)
    return listing_data(item)


@app.patch("/api/listings/{listing_id}/status")
def update_status(listing_id: int, data: StatusIn, user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]):
    item = db.get(Listing, listing_id)
    if not item:
        raise HTTPException(404, "Вещь не найдена")
    if item.owner_id != user.id:
        raise HTTPException(403, "Это не ваша вещь")
    item.status = data.status
    db.commit()
    return listing_data(item)


@app.delete("/api/listings/{listing_id}", status_code=204)
def delete_listing(listing_id: int, user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]):
    item = db.get(Listing, listing_id)
    if not item:
        raise HTTPException(404, "Вещь не найдена")
    if item.owner_id != user.id and not user.is_admin:
        raise HTTPException(403, "Это не ваша вещь")
    db.delete(item)
    db.commit()


@app.get("/api/me/telegram")
def telegram_settings(user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]):
    sub = db.scalar(select(Subscription).where(Subscription.user_id == user.id))
    return {"connected": bool(sub), "categories": sub.categories.split("|") if sub and sub.categories else [], "enabled": sub.enabled if sub else False, "bot_url": f"https://t.me/{settings.bot_username}?start={telegram_code(user.id)}" if settings.bot_username else ""}


@app.put("/api/me/telegram")
def telegram_preferences(data: PreferencesIn, user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]):
    sub = db.scalar(select(Subscription).where(Subscription.user_id == user.id))
    if not sub:
        raise HTTPException(400, "Сначала подключите Telegram")
    sub.categories = "|".join(data.categories)
    sub.enabled = data.enabled
    db.commit()
    return {"connected": True, "categories": data.categories, "enabled": data.enabled}


def seed_demo():
    with SessionLocal() as db:
        if db.scalar(select(func.count(User.id))):
            return
        demo = User(name="Команда CURU", email="demo@curu.local", password_hash=hash_password(secrets.token_urlsafe(24)), faculty="Caspian University", contact="", bio="Передаём вещам новую историю")
        db.add(demo)
        db.flush()
        samples = [
            ("Худи оверсайз", "Одежда", "Отличное состояние", "Главный корпус", "Тёплое худи, размер M. Носила пару раз, чистое и без дефектов.", "https://images.unsplash.com/photo-1556821840-3a63f95609a7?w=900&q=85"),
            ("Учебник по экономике", "Книги", "Хорошее состояние", "Библиотека", "Учебник с пометками карандашом. Подойдёт для первого курса.", "https://images.unsplash.com/photo-1497633762265-9d179a990aa6?w=900&q=85"),
            ("Настольная лампа", "Для дома", "Отличное состояние", "Корпус на Сейфуллина", "Рабочая лампа для учебного стола. Лампочка в комплекте.", "https://images.unsplash.com/photo-1507473885765-e6ed057f782c?w=900&q=85"),
            ("Наушники проводные", "Гаджеты", "Хорошее состояние", "Главный корпус", "Проводные наушники, звук работает отлично. Отдам в чехле.", "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=900&q=85"),
            ("Рюкзак для учёбы", "Одежда", "Хорошее состояние", "Главный корпус", "Вместительный рюкзак для ноутбука и книг. Все молнии работают.", "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=900&q=85"),
            ("Набор блокнотов", "Для учёбы", "Новое", "Библиотека", "Три чистых блокнота в клетку. Забирайте для нового семестра.", "https://images.unsplash.com/photo-1455390582262-044cdead277a?w=900&q=85"),
        ]
        for index, (title, category, condition, location, description, image) in enumerate(samples):
            db.add(Listing(owner_id=demo.id, title=title, category=category, condition=condition, location=location, description=description, image=image, created_at=datetime.now(timezone.utc) - timedelta(hours=index * 5)))
        db.commit()
