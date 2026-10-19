import asyncio, base64, hashlib, hmac, os, secrets, json
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Literal
import jwt
from aiogram import Bot
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import DateTime, func, inspect, or_, select, text
from sqlalchemy.orm import Session
from config import config, settings
from .database.models import *
from .event_models import Event, Ticket, Review, EventInterest, EventNotification
from .events import router_for, lifecycle
from .database.db import get_db, engine, SessionLocal
from .bot import notify_admin_for_review, run_bot
from .ai.moderation import safe_moderate_listing
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


def optional_user(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)], db: Annotated[Session, Depends(get_db)]) -> User | None:
    if credentials is None:
        return None
    try:
        return current_user(credentials, db)
    except HTTPException:
        return None


def user_data(user: User) -> dict:
    return {"id": user.id, "name": user.name, "email": user.email, "education_level": user.education_level, "study_group": user.study_group, "contact": user.contact, "bio": user.bio, "is_admin": user.is_admin, "is_organizer": user.is_organizer, "created_at": user.created_at.isoformat()}


def migrate_hub_columns() -> None:
    additions = {
        'listings': {'price': 'INTEGER NOT NULL DEFAULT 0'},
        'events': {'banner': "TEXT NOT NULL DEFAULT ''", 'end_date': DateTime(timezone=True).compile(dialect=engine.dialect)},
    }
    for table, fields in additions.items():
        if inspect(engine).has_table(table):
            existing = {c['name'] for c in inspect(engine).get_columns(table)}
            with engine.begin() as connection:
                for name, definition in fields.items():
                    if name not in existing:
                        connection.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {definition}'))


def migrate_user_columns() -> None:
    # create_all does not add columns to existing installations.
    if inspect(engine).has_table("users"):
        columns = {column["name"] for column in inspect(engine).get_columns("users")}
        with engine.begin() as connection:
            if "is_organizer" not in columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN is_organizer BOOLEAN NOT NULL DEFAULT FALSE"))
            if "is_admin" not in columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT FALSE"))
            if "education_level" not in columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN education_level VARCHAR(20) NOT NULL DEFAULT ''"))
            if "study_group" not in columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN study_group VARCHAR(40) NOT NULL DEFAULT ''"))
    if inspect(engine).has_table("listings"):
        columns = {column["name"] for column in inspect(engine).get_columns("listings")}
        if "moderation_reason" not in columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE listings ADD COLUMN moderation_reason TEXT NOT NULL DEFAULT ''"))


def prepare_admin() -> None:
    if not settings.admin_password:
        return
    if len(settings.admin_password) < 12:
        raise RuntimeError("ADMIN_PASSWORD must be at least 12 characters")
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == settings.admin_email))
        if not user:
            user = User(name="Команда CaspianHub", email=settings.admin_email, faculty="Caspian University", contact="", bio="Команда CaspianHub")
            db.add(user)
        if user.name == "Команда CURU":
            user.name = "Команда CaspianHub"
        if user.bio == "Команда CURU":
            user.bio = "Команда CaspianHub"
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
        "price": item.price,
        "status": item.status,
        "moderation_reason": item.moderation_reason,
        "created_at": item.created_at.isoformat(),
        "owner": user_data(item.owner),
    }

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    Base.metadata.create_all(engine)
    migrate_user_columns()
    migrate_hub_columns()
    if os.getenv("SEED_DEMO", "true").lower() == "true":
        seed_demo()
    prepare_admin()
    task = asyncio.create_task(run_bot()) if settings.bot_token else None

    event_task = asyncio.create_task(lifecycle())
    yield
    event_task.cancel()
    try:
        await event_task
    except asyncio.CancelledError:
        pass

    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="CaspianHub API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[v.strip() for v in os.getenv("FRONTEND_URL", "http://localhost:5173").split(",")], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.get("/api/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/api/categories")
def categories() -> list[str]:
    return config.categories


@app.get("/api/support")
def support_info() -> dict[str, str]:
    return {
        "bot_url": f"https://t.me/{settings.bot_username}?start=support"
        if settings.bot_username and settings.bot_token and settings.support_chat_id
        else ""
    }


@app.post("/api/auth/register", status_code=201)
def register(data: UserIn, db: Annotated[Session, Depends(get_db)]) -> dict[str, Any]:
    email = data.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "Этот email уже зарегистрирован")
    user = User(name=data.name.strip(), email=email, password_hash=hash_password(data.password), education_level=data.education_level, study_group=data.study_group.strip(), contact=data.contact.strip())
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"token": token_for(user.id), "user": user_data(user)}


@app.post("/api/auth/login")
def login(data: LoginIn, db: Annotated[Session, Depends(get_db)]) -> dict[str, Any]:
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Неверный email или пароль")
    return {"token": token_for(user.id), "user": user_data(user)}


@app.get("/api/me")
def me(user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]) -> dict[str, Any]:
    mine = db.scalars(select(Listing).where(Listing.owner_id == user.id).order_by(Listing.created_at.desc())).all()
    return {**user_data(user), "listings": [listing_data(item) for item in mine], "stats": {"published": sum(item.status != "pending" for item in mine), "given": sum(item.status == "given" for item in mine), "active": sum(item.status in ("available", "reserved") for item in mine)}}


@app.patch("/api/me")
def update_me(data: ProfileIn, user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]) -> dict[str, Any]:
    for key, value in data.model_dump().items():
        if value is not None:
            setattr(user, key, value.strip())
    db.commit()
    return user_data(user)


@app.get("/api/users/{user_id}")
def public_user(user_id: int, db: Annotated[Session, Depends(get_db)]) -> dict[str, Any]:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "Студент не найден")
    items = db.scalars(select(Listing).where(Listing.owner_id == user_id, Listing.status != "pending").order_by(Listing.created_at.desc())).all()
    return {**user_data(user), "listings": [listing_data(item) for item in items], "stats": {"published": len(items), "given": sum(item.status == "given" for item in items)}}


@app.get("/api/listings")
def listings(db: Annotated[Session, Depends(get_db)], viewer: Annotated[User | None, Depends(optional_user)], category: str | None = None, q: str | None = None, status: str = "available", limit: int = Query(60, ge=1, le=100), offset: int = Query(0, ge=0), price_type: Literal["all", "free", "paid"] = "all") -> list[dict[str, Any]]:
    stmt = select(Listing).order_by(Listing.created_at.desc(), Listing.id.desc())
    if price_type == "free":
        stmt = stmt.where(Listing.price == 0)
    elif price_type == "paid":
        stmt = stmt.where(Listing.price > 0)
    if category and category != "Все":
        stmt = stmt.where(Listing.category == category)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(or_(Listing.title.ilike(pattern), Listing.description.ilike(pattern)))
    if status != "all":
        stmt = stmt.where(Listing.status == status)
    if viewer is None or not viewer.is_admin:
        stmt = stmt.where(Listing.status != "pending")
    return [listing_data(item) for item in db.scalars(stmt.offset(offset).limit(limit)).all()]


@app.get("/api/listings/{listing_id}")
def listing(listing_id: int, db: Annotated[Session, Depends(get_db)], viewer: Annotated[User | None, Depends(optional_user)]) -> dict[str, Any]:
    item = db.get(Listing, listing_id)
    if not item:
        raise HTTPException(404, "Вещь не найдена")
    if item.status == "pending" and (viewer is None or (viewer.id != item.owner_id and not viewer.is_admin)):
        raise HTTPException(404, "Вещь не найдена")
    return listing_data(item)


async def notify_subscribers(listing_id: int) -> None:
    if not settings.bot_token:
        return
    with SessionLocal() as db:
        item = db.get(Listing, listing_id)
        if not item:
            return
        subs = db.scalars(select(Subscription).where(Subscription.enabled == True, Subscription.user_id != item.owner_id)).all()
        telegram_subs = db.scalars(select(TelegramSubscription).where(TelegramSubscription.enabled == True)).all()
        recipients = sorted(
            {s.chat_id for s in subs if item.category in s.categories.split("|")}
            | {s.chat_id for s in telegram_subs if item.category in s.categories.split("|")}
        )
        title, category, location = item.title, item.category, item.location
        price_label = f"{item.price:,} ₸".replace(",", " ") if item.price else "Бесплатно"
    bot = Bot(settings.bot_token)
    frontend = os.getenv("FRONTEND_URL", "http://localhost:5173").split(",")[0].strip().rstrip("/")
    try:
        for chat_id in recipients:
            try:
                await bot.send_message(chat_id, f"Новое объявление в маркете CaspianHub\n\n{title}\n{price_label}\n{category} · {location}\n\n{frontend}/market/{listing_id}")
            except Exception:
                pass
    finally:
        await bot.session.close()


@app.post("/api/listings", status_code=201)
async def create_listing(data: ListingIn, tasks: BackgroundTasks, user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]) -> dict[str, Any]:
    if not user.contact.strip():
        raise HTTPException(400, "Сначала добавьте контакт для связи в профиле")
    if (not settings.mistral_api_key and not settings.agnes_api_key) or not settings.bot_token or settings.support_chat_id is None:
        raise HTTPException(503, "Публикация временно недоступна: модерация не настроена")
    
    result = await safe_moderate_listing(data)
    status = "available" if result.decision == "approve" else "pending"

    item = Listing(**data.model_dump(), owner_id=user.id, status=status, moderation_reason=result.reason if status == "pending" else "")
    db.add(item)
    db.commit()
    db.refresh(item)

    if status == "pending":
        await notify_admin_for_review(item.id)
    else:
        tasks.add_task(notify_subscribers, item.id)
    return listing_data(item)


@app.patch("/api/listings/{listing_id}/status")
def update_status(listing_id: int, data: StatusIn, user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]) -> dict[str, Any]:
    item = db.get(Listing, listing_id)
    if not item:
        raise HTTPException(404, "Вещь не найдена")
    if item.owner_id != user.id:
        raise HTTPException(403, "Это не ваша вещь")
    if item.status == "pending":
        raise HTTPException(409, "Объявление ожидает решения модератора")
    item.status = data.status
    db.commit()
    return listing_data(item)


@app.delete("/api/listings/{listing_id}", status_code=204)
def delete_listing(listing_id: int, user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]) -> None:
    item = db.get(Listing, listing_id)
    if not item:
        raise HTTPException(404, "Вещь не найдена")
    if item.owner_id != user.id and not user.is_admin:
        raise HTTPException(403, "Это не ваша вещь")
    db.delete(item)
    db.commit()


@app.post("/api/admin/listings/{listing_id}/approve")
def approve_listing(listing_id: int, tasks: BackgroundTasks, user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]) -> dict[str, Any]:
    if not user.is_admin:
        raise HTTPException(403, "Требуются права администратора")
    item = db.scalar(select(Listing).where(Listing.id == listing_id).with_for_update())
    if item is None:
        raise HTTPException(404, "Объявление не найдено")
    if item.status != "pending":
        raise HTTPException(409, "Объявление уже обработано")
    item.status = "available"
    db.commit()
    tasks.add_task(notify_subscribers, item.id)
    return listing_data(item)


@app.get("/api/me/telegram")
def telegram_settings(user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]) -> dict[str, Any]:
    sub = db.scalar(select(Subscription).where(Subscription.user_id == user.id))
    return {"connected": bool(sub), "categories": sub.categories.split("|") if sub and sub.categories else [], "enabled": sub.enabled if sub else False, "bot_url": f"https://t.me/{settings.bot_username}?start={telegram_code(user.id)}" if settings.bot_username else ""}


@app.put("/api/me/telegram")
def telegram_preferences(data: PreferencesIn, user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]) -> dict[str, Any]:
    sub = db.scalar(select(Subscription).where(Subscription.user_id == user.id))
    if not sub:
        raise HTTPException(400, "Сначала подключите Telegram")
    sub.categories = "|".join(data.categories)
    sub.enabled = data.enabled
    db.commit()
    return {"connected": True, "categories": data.categories, "enabled": data.enabled}


def seed_demo() -> None:
    with SessionLocal() as db:
        if db.scalar(select(func.count(User.id))):
            return
        demo = User(name="Команда CaspianHub", email="demo@curu.local", password_hash=hash_password(secrets.token_urlsafe(24)), faculty="Caspian University", contact="", bio="Передаём вещам новую историю")
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

app.include_router(router_for(current_user))
