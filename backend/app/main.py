import asyncio
import base64
import hashlib
import hmac
import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal

import jwt
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BotCommand, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, create_engine, func, inspect, or_, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./curu.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
SECRET = os.getenv("JWT_SECRET", "dev-only-change-me")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "")
SUPPORT_CHAT_ID = os.getenv("SUPPORT_CHAT_ID", "").strip()
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "demo@curu.local").strip().lower()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
CATEGORIES = ["Одежда", "Гаджеты", "Книги", "Для учёбы", "Для дома", "Другое"]
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    faculty: Mapped[str] = mapped_column(String(120), default="")
    education_level: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    study_group: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    contact: Mapped[str] = mapped_column(String(200), default="")
    bio: Mapped[str] = mapped_column(String(400), default="")
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    listings: Mapped[list["Listing"]] = relationship(back_populates="owner")


class Listing(Base):
    __tablename__ = "listings"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(2000))
    category: Mapped[str] = mapped_column(String(40), index=True)
    condition: Mapped[str] = mapped_column(String(40))
    location: Mapped[str] = mapped_column(String(120))
    image: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="available", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    owner: Mapped[User] = relationship(back_populates="listings")


class Subscription(Base):
    __tablename__ = "subscriptions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    chat_id: Mapped[str] = mapped_column(String(40), unique=True)
    categories: Mapped[str] = mapped_column(String(300), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class TelegramSubscription(Base):
    __tablename__ = "telegram_subscriptions"
    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    categories: Mapped[str] = mapped_column(String(300), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class SupportMessage(Base):
    __tablename__ = "support_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    admin_message_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    user_chat_id: Mapped[str] = mapped_column(String(40))


class UserIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    education_level: Literal["university", "college"]
    study_group: str = Field(default="", max_length=40)
    contact: str = Field(default="", max_length=200)


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str


class ProfileIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    education_level: Literal["university", "college"] | None = None
    study_group: str = Field(default="", max_length=40)
    contact: str = Field(default="", max_length=200)
    bio: str = Field(default="", max_length=400)


class ListingIn(BaseModel):
    title: str = Field(min_length=3, max_length=100)
    description: str = Field(min_length=10, max_length=2000)
    category: str
    condition: str = Field(min_length=2, max_length=40)
    location: str = Field(min_length=2, max_length=120)
    image: str = Field(default="", max_length=2_800_000)

    @field_validator("category")
    @classmethod
    def category_valid(cls, value: str) -> str:
        if value not in CATEGORIES:
            raise ValueError("Неизвестная категория")
        return value

    @field_validator("image")
    @classmethod
    def image_valid(cls, value: str) -> str:
        if value and not (value.startswith("data:image/jpeg;base64,") or value.startswith("data:image/png;base64,") or value.startswith("data:image/webp;base64,") or value.startswith("https://")):
            raise ValueError("Нужно изображение JPEG, PNG, WebP или HTTPS-ссылка")
        return value


class StatusIn(BaseModel):
    status: Literal["available", "reserved", "given"]


class PreferencesIn(BaseModel):
    categories: list[str]
    enabled: bool = True

    @field_validator("categories")
    @classmethod
    def categories_valid(cls, value: list[str]) -> list[str]:
        if any(category not in CATEGORIES for category in value):
            raise ValueError("Неизвестная категория")
        return list(dict.fromkeys(value))


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
    return jwt.encode({"sub": str(user_id), "purpose": purpose, "exp": datetime.now(timezone.utc) + timedelta(minutes=minutes)}, SECRET, algorithm="HS256")


def telegram_code(user_id: int) -> str:
    payload = f"{user_id:x}.{int((datetime.now(timezone.utc) + timedelta(minutes=15)).timestamp()):x}"
    signature = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:20]
    return f"{payload}.{signature}"


def user_from_telegram_code(code: str) -> int:
    try:
        user_hex, expiry_hex, signature = code.split(".")
        payload = f"{user_hex}.{expiry_hex}"
        expected = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:20]
        if not hmac.compare_digest(signature, expected) or int(expiry_hex, 16) < datetime.now(timezone.utc).timestamp():
            raise ValueError()
        return int(user_hex, 16)
    except (ValueError, TypeError):
        raise ValueError("Invalid Telegram link")


def get_db():
    with SessionLocal() as db:
        yield db


bearer = HTTPBearer(auto_error=False)


def current_user(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)], db: Annotated[Session, Depends(get_db)]) -> User:
    if not credentials:
        raise HTTPException(401, "Войдите в аккаунт")
    try:
        payload = jwt.decode(credentials.credentials, SECRET, algorithms=["HS256"])
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
    if not ADMIN_PASSWORD:
        return
    if len(ADMIN_PASSWORD) < 12:
        raise RuntimeError("ADMIN_PASSWORD must be at least 12 characters")
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == ADMIN_EMAIL))
        if not user:
            user = User(name="Команда CURU", email=ADMIN_EMAIL, faculty="Caspian University", contact="", bio="Команда CURU")
            db.add(user)
        user.password_hash = hash_password(ADMIN_PASSWORD)
        user.is_admin = True
        db.commit()


def listing_data(item: Listing) -> dict:
    return {"id": item.id, "title": item.title, "description": item.description, "category": item.category, "condition": item.condition, "location": item.location, "image": item.image, "status": item.status, "created_at": item.created_at.isoformat(), "owner": user_data(item.owner)}


bot_router = Router()


class SupportState(StatesGroup):
    waiting_for_message = State()


async def start_support(message: Message, state: FSMContext):
    if message.chat.type != "private":
        await message.answer("Открой бота в личных сообщениях, чтобы написать в поддержку.")
        return
    if not SUPPORT_CHAT_ID:
        await message.answer("Поддержка пока недоступна. Попробуй позже.")
        return
    await state.set_state(SupportState.waiting_for_message)
    await message.answer("Напиши свой вопрос одним сообщением. Команда CURU ответит здесь. Для выхода отправь /cancel.")


def preference_keyboard(sub: Subscription | TelegramSubscription) -> InlineKeyboardMarkup:
    selected = set(filter(None, sub.categories.split("|")))
    rows = [[InlineKeyboardButton(text=f"{'✅' if category in selected else '▫️'} {category}", callback_data=f"cat:{i}")] for i, category in enumerate(CATEGORIES)]
    rows.append([InlineKeyboardButton(text="🔔 Уведомления включены" if sub.enabled else "🔕 Уведомления выключены", callback_data="toggle")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def chat_subscription(db: Session, chat_id: str, create: bool = False) -> Subscription | TelegramSubscription | None:
    sub = db.scalar(select(Subscription).where(Subscription.chat_id == chat_id))
    if sub:
        return sub
    sub = db.scalar(select(TelegramSubscription).where(TelegramSubscription.chat_id == chat_id))
    if not sub and create:
        sub = TelegramSubscription(chat_id=chat_id, categories="", enabled=True)
        db.add(sub)
        db.commit()
    return sub


async def show_categories(message: Message):
    if message.chat.type != "private":
        await message.answer("Открой бота в личных сообщениях, чтобы настроить уведомления.")
        return
    with SessionLocal() as db:
        sub = chat_subscription(db, str(message.chat.id), create=True)
        await message.answer("Выбери интересующие категории кнопками ниже. Отмеченные категории будут приносить уведомления о новых вещах. Настройки можно открыть снова командой /categories.", reply_markup=preference_keyboard(sub))


@bot_router.message(CommandStart())
async def bot_start(message: Message, state: FSMContext):
    code = (message.text or "").split(maxsplit=1)
    if len(code) == 2 and code[1] == "support":
        await start_support(message, state)
        return
    if len(code) != 2:
        await show_categories(message)
        return
    try:
        user_id = user_from_telegram_code(code[1])
    except ValueError:
        await message.answer("Ссылка на профиль устарела. Новую можно получить на сайте; уведомления доступны и без привязки аккаунта.")
        await show_categories(message)
        return
    with SessionLocal() as db:
        if not db.get(User, user_id):
            await message.answer("Аккаунт не найден.")
            await show_categories(message)
            return
        old_chat = db.scalar(select(Subscription).where(Subscription.chat_id == str(message.chat.id)))
        if old_chat and old_chat.user_id != user_id:
            db.delete(old_chat)
            db.flush()
        sub = db.scalar(select(Subscription).where(Subscription.user_id == user_id))
        standalone = db.scalar(select(TelegramSubscription).where(TelegramSubscription.chat_id == str(message.chat.id)))
        if not sub:
            sub = Subscription(user_id=user_id, chat_id=str(message.chat.id), categories=standalone.categories if standalone else "", enabled=standalone.enabled if standalone else True)
            db.add(sub)
        else:
            sub.chat_id = str(message.chat.id)
            if standalone:
                sub.categories = standalone.categories
                sub.enabled = standalone.enabled
        if standalone:
            db.delete(standalone)
        db.commit()
        await message.answer("Аккаунт подключён. Выбери категории для уведомлений:", reply_markup=preference_keyboard(sub))


@bot_router.message(Command("categories"))
async def bot_categories(message: Message):
    await show_categories(message)


@bot_router.message(Command("support"))
async def bot_support(message: Message, state: FSMContext):
    await start_support(message, state)


@bot_router.message(Command("cancel"))
async def bot_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Обращение закрыто. Чтобы написать снова, отправь /support.")


@bot_router.message(Command("chatid"))
async def bot_chat_id(message: Message):
    await message.answer(f"ID этого чата: {message.chat.id}")


@bot_router.message(SupportState.waiting_for_message)
async def bot_support_message(message: Message):
    if not message.text:
        await message.answer("Пожалуйста, отправь вопрос текстом.")
        return
    if len(message.text) > 3500:
        await message.answer("Сообщение слишком длинное. Сократи его до 3500 символов.")
        return
    sender = message.from_user.full_name if message.from_user else "Пользователь"
    username = f" (@{message.from_user.username})" if message.from_user and message.from_user.username else ""
    try:
        sent = await message.bot.send_message(int(SUPPORT_CHAT_ID), f"📩 Поддержка CURU\nОт: {sender}{username}\n\n{message.text}\n\nОтветь на это сообщение реплаем.")
    except Exception:
        await message.answer("Не удалось отправить вопрос. Попробуй позже.")
        return
    with SessionLocal() as db:
        db.add(SupportMessage(admin_message_id=sent.message_id, user_chat_id=str(message.chat.id)))
        db.commit()
    await message.answer("Вопрос отправлен команде CURU. Ответ придёт сюда. Можешь написать ещё сообщение или отправить /cancel.")


@bot_router.message(F.reply_to_message)
async def bot_support_reply(message: Message):
    if not SUPPORT_CHAT_ID or str(message.chat.id) != SUPPORT_CHAT_ID or not message.text:
        return
    with SessionLocal() as db:
        original = db.scalar(select(SupportMessage).where(SupportMessage.admin_message_id == message.reply_to_message.message_id))
        user_chat_id = original.user_chat_id if original else None
    if not user_chat_id:
        return
    try:
        await message.bot.send_message(int(user_chat_id), f"💬 Ответ команды CURU:\n\n{message.text}")
    except Exception:
        await message.answer("Не удалось доставить ответ пользователю.")
        return
    await message.reply("Ответ отправлен пользователю.")


@bot_router.callback_query(F.data.startswith("cat:") | (F.data == "toggle"))
async def bot_preference(callback: CallbackQuery):
    with SessionLocal() as db:
        sub = chat_subscription(db, str(callback.message.chat.id))
        if not sub:
            await callback.answer("Отправь /start, чтобы выбрать категории", show_alert=True)
            return
        if callback.data == "toggle":
            sub.enabled = not sub.enabled
        else:
            try:
                index = int(callback.data.split(":")[1])
                category = CATEGORIES[index] if 0 <= index < len(CATEGORIES) else None
            except (ValueError, IndexError):
                category = None
            if category is None:
                await callback.answer("Категория не найдена")
                return
            selected = set(filter(None, sub.categories.split("|")))
            selected.symmetric_difference_update({category})
            sub.categories = "|".join(c for c in CATEGORIES if c in selected)
        db.commit()
        await callback.message.edit_reply_markup(reply_markup=preference_keyboard(sub))
        await callback.answer("Сохранено")


async def run_bot():
    bot = Bot(BOT_TOKEN)
    dispatcher = Dispatcher()
    dispatcher.include_router(bot_router)
    try:
        await bot.set_my_commands([BotCommand(command="start", description="Выбрать категории"), BotCommand(command="categories", description="Настроить уведомления"), BotCommand(command="support", description="Написать в поддержку"), BotCommand(command="cancel", description="Завершить обращение")])
        await dispatcher.start_polling(bot, handle_signals=False)
    finally:
        await bot.session.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    migrate_user_columns()
    if os.getenv("SEED_DEMO", "true").lower() == "true":
        seed_demo()
    prepare_admin()
    task = asyncio.create_task(run_bot()) if BOT_TOKEN else None
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
    return CATEGORIES


@app.get("/api/support")
def support_info():
    return {"bot_url": f"https://t.me/{BOT_USERNAME}?start=support" if BOT_USERNAME and BOT_TOKEN and SUPPORT_CHAT_ID else ""}


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
    if not BOT_TOKEN:
        return
    with SessionLocal() as db:
        item = db.get(Listing, listing_id)
        if not item:
            return
        subs = db.scalars(select(Subscription).where(Subscription.enabled == True, Subscription.user_id != item.owner_id)).all()
        telegram_subs = db.scalars(select(TelegramSubscription).where(TelegramSubscription.enabled == True)).all()
        recipients = sorted({s.chat_id for s in [*subs, *telegram_subs] if item.category in s.categories.split("|")})
        title, category, location = item.title, item.category, item.location
    bot = Bot(BOT_TOKEN)
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
    return {"connected": bool(sub), "categories": sub.categories.split("|") if sub and sub.categories else [], "enabled": sub.enabled if sub else False, "bot_url": f"https://t.me/{BOT_USERNAME}?start={telegram_code(user.id)}" if BOT_USERNAME else ""}


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
