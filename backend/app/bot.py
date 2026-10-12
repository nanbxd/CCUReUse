from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import BotCommand, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select
from config import config, settings
from aiogram.fsm.state import State, StatesGroup
from .database.models import *
from .database.db import SessionLocal
import hashlib, hmac

class SupportState(StatesGroup):
    waiting_for_message = State()

def user_from_telegram_code(code: str) -> int:
    try:
        user_hex, expiry_hex, signature = code.split(".")
        payload = f"{user_hex}.{expiry_hex}"
        expected = hmac.new(settings.jwt_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()[:20]
        if not hmac.compare_digest(signature, expected) or int(expiry_hex, 16) < datetime.now(timezone.utc).timestamp():
            raise ValueError()
        return int(user_hex, 16)
    except (ValueError, TypeError):
        raise ValueError("Invalid Telegram link")

async def start_support(message: Message, state: FSMContext) -> None:
    if message.chat.type != "private":
        await message.answer("Открой бота в личных сообщениях, чтобы написать в поддержку.")
        return
    if not settings.support_chat_id:
        await message.answer("Поддержка пока недоступна. Попробуй позже.")
        return
    await state.set_state(SupportState.waiting_for_message)
    await message.answer("Напиши свой вопрос одним сообщением. Команда CURU ответит здесь. Для выхода отправь /cancel.")


def preference_keyboard(sub: Subscription | TelegramSubscription) -> InlineKeyboardMarkup:
    selected = set(filter(None, sub.categories.split("|")))
    rows = [[InlineKeyboardButton(text=f"{'✅' if category in selected else '▫️'} {category}", callback_data=f"cat:{i}")] for i, category in enumerate(config.categories)]
    rows.append([InlineKeyboardButton(text="🔔 Уведомления включены" if sub.enabled else "🔕 Уведомления выключены", callback_data="toggle")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def chat_subscription(db: Session, chat_id: str, create: bool = False) -> Subscription | TelegramSubscription | None:
    sub: Subscription | TelegramSubscription | None = db.scalar(select(Subscription).where(Subscription.chat_id == chat_id))
    if sub:
        return sub
    sub = db.scalar(select(TelegramSubscription).where(TelegramSubscription.chat_id == chat_id))
    if not sub and create:
        sub = TelegramSubscription(chat_id=chat_id, categories="", enabled=True)
        db.add(sub)
        db.commit()
    return sub


async def show_categories(message: Message) -> None:
    if message.chat.type != "private":
        await message.answer("Открой бота в личных сообщениях, чтобы настроить уведомления.")
        return
    with SessionLocal() as db:
        sub = chat_subscription(db, str(message.chat.id), create=True)
        if sub is None:
            return
        await message.answer("Выбери интересующие категории кнопками ниже. Отмеченные категории будут приносить уведомления о новых вещах. Настройки можно открыть снова командой /categories.", reply_markup=preference_keyboard(sub))

bot_router = Router()

@bot_router.message(CommandStart())
async def bot_start(message: Message, state: FSMContext) -> None:
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
async def bot_categories(message: Message) -> None:
    await show_categories(message)


@bot_router.message(Command("support"))
async def bot_support(message: Message, state: FSMContext) -> None:
    await start_support(message, state)


@bot_router.message(Command("cancel"))
async def bot_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Обращение закрыто. Чтобы написать снова, отправь /support.")


@bot_router.message(Command("chatid"))
async def bot_chat_id(message: Message) -> None:
    await message.answer(f"ID этого чата: {message.chat.id}")


@bot_router.message(SupportState.waiting_for_message)
async def bot_support_message(message: Message) -> None:
    if message.bot is None or settings.support_chat_id is None:
        return
    if not message.text:
        await message.answer("Пожалуйста, отправь вопрос текстом.")
        return
    if len(message.text) > 3500:
        await message.answer("Сообщение слишком длинное. Сократи его до 3500 символов.")
        return
    sender = message.from_user.full_name if message.from_user else "Пользователь"
    username = f" (@{message.from_user.username})" if message.from_user and message.from_user.username else ""
    try:
        sent = await message.bot.send_message(settings.support_chat_id, f"📩 Поддержка CURU\nОт: {sender}{username}\n\n{message.text}\n\nОтветь на это сообщение реплаем.")
    except Exception:
        await message.answer("Не удалось отправить вопрос. Попробуй позже.")
        return
    with SessionLocal() as db:
        db.add(SupportMessage(admin_message_id=sent.message_id, user_chat_id=str(message.chat.id)))
        db.commit()
    await message.answer("Вопрос отправлен команде CURU. Ответ придёт сюда. Можешь написать ещё сообщение или отправить /cancel.")


@bot_router.message(F.reply_to_message)
async def bot_support_reply(message: Message) -> None:
    if not settings.support_chat_id or str(message.chat.id) != str(settings.support_chat_id) or not message.text or message.reply_to_message is None or message.bot is None:
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
async def bot_preference(callback: CallbackQuery) -> None:
    if not isinstance(callback.message, Message) or callback.data is None:
        await callback.answer()
        return
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
                category = config.categories[index] if 0 <= index < len(config.categories) else None
            except (ValueError, IndexError):
                category = None
            if category is None:
                await callback.answer("Категория не найдена")
                return
            selected = set(filter(None, sub.categories.split("|")))
            selected.symmetric_difference_update({category})
            sub.categories = "|".join(c for c in config.categories if c in selected)
        db.commit()
        await callback.message.edit_reply_markup(reply_markup=preference_keyboard(sub))
        await callback.answer("Сохранено")


async def run_bot() -> None:
    bot = Bot(settings.bot_token)
    dispatcher = Dispatcher()
    dispatcher.include_router(bot_router)
    try:
        await bot.set_my_commands([BotCommand(command="start", description="Выбрать категории"), BotCommand(command="categories", description="Настроить уведомления"), BotCommand(command="support", description="Написать в поддержку"), BotCommand(command="cancel", description="Завершить обращение")])
        await dispatcher.start_polling(bot, handle_signals=False)
    finally:
        await bot.session.close()
