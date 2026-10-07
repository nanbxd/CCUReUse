import asyncio
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

test_dir = tempfile.TemporaryDirectory()
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(test_dir.name, "curu-test.db").replace("\\", "/")
os.environ["SEED_DEMO"] = "false"
os.environ["BOT_TOKEN"] = ""
os.environ["JWT_SECRET"] = "test-secret-with-at-least-thirty-two-characters"
os.environ["ADMIN_PASSWORD"] = "local-test-admin-password"

from app.main import (  # noqa: E402
    SessionLocal, Subscription, TelegramSubscription, app, bot_categories, bot_preference,
    bot_start, bot_support_message, bot_support_reply, engine, notify_subscribers,
    telegram_code, user_from_telegram_code,
)


class CuruApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client_context.__exit__(None, None, None)
        engine.dispose()
        test_dir.cleanup()

    def test_register_publish_search_and_status(self):
        response = self.client.post("/api/auth/register", json={"name": "Алия Тест", "email": "aliya@example.com", "password": "password123", "education_level": "university", "study_group": "ИС-22-1", "contact": "@aliya"})
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["user"]["study_group"], "ИС-22-1")
        token = response.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        self.assertEqual(self.client.post("/api/auth/register", json={"name": "Алия Тест", "email": "aliya@example.com", "password": "password123", "education_level": "university"}).status_code, 409)
        self.assertEqual(self.client.post("/api/auth/login", json={"email": "aliya@example.com", "password": "password123"}).status_code, 200)
        response = self.client.post("/api/listings", headers=headers, json={"title": "Учебник физики", "description": "Хороший учебник для первого курса", "category": "Книги", "condition": "Хорошее состояние", "location": "Библиотека", "image": ""})
        self.assertEqual(response.status_code, 201, response.text)
        item_id = response.json()["id"]
        self.assertEqual(len(self.client.get("/api/listings?category=Книги&q=физики").json()), 1)
        self.assertEqual(len(self.client.get("/api/listings?category=Одежда").json()), 0)
        self.assertEqual(self.client.patch(f"/api/listings/{item_id}/status", headers=headers, json={"status": "given"}).json()["status"], "given")
        self.assertEqual(self.client.get("/api/me", headers=headers).json()["stats"]["given"], 1)
        self.assertEqual(len(self.client.get("/api/listings").json()), 0)
        self.assertEqual(self.client.delete(f"/api/listings/{item_id}", headers=headers).status_code, 204)

    def test_telegram_link_is_short_and_verifiable(self):
        code = telegram_code(123)
        self.assertLessEqual(len(code), 64)
        self.assertEqual(user_from_telegram_code(code), 123)
        with self.assertRaises(ValueError):
            user_from_telegram_code(code + "broken")

    def test_admin_can_delete_another_users_listing(self):
        owner = self.client.post("/api/auth/register", json={"name": "Другой студент", "email": "owner@example.com", "password": "password123", "education_level": "college", "contact": "@owner"}).json()
        owner_headers = {"Authorization": f"Bearer {owner['token']}"}
        item = self.client.post("/api/listings", headers=owner_headers, json={"title": "Чужая вещь", "description": "Вещь в хорошем состоянии", "category": "Книги", "condition": "Хорошее состояние", "location": "Библиотека"}).json()
        admin_response = self.client.post("/api/auth/login", json={"email": "demo@curu.local", "password": "local-test-admin-password"})
        self.assertEqual(admin_response.status_code, 200, admin_response.text)
        self.assertTrue(admin_response.json()["user"]["is_admin"])
        admin_headers = {"Authorization": f"Bearer {admin_response.json()['token']}"}
        self.assertEqual(self.client.delete(f"/api/listings/{item['id']}").status_code, 401)
        outsider = self.client.post("/api/auth/register", json={"name": "Обычный пользователь", "email": "outsider@example.com", "password": "password123", "education_level": "university", "is_admin": True}).json()
        self.assertFalse(outsider["user"]["is_admin"])
        self.assertEqual(self.client.delete(f"/api/listings/{item['id']}", headers={"Authorization": f"Bearer {outsider['token']}"}).status_code, 403)
        self.assertEqual(self.client.delete(f"/api/listings/{item['id']}", headers=admin_headers).status_code, 204)
        self.assertEqual(self.client.get(f"/api/listings/{item['id']}").status_code, 404)

    def test_registration_rejects_unlisted_school_type_and_allows_group_edit(self):
        base = {"name": "Новый студент", "email": "group@example.com", "password": "password123"}
        self.assertEqual(self.client.post("/api/auth/register", json={**base, "education_level": "school"}).status_code, 422)
        self.assertEqual(self.client.post("/api/auth/register", json=base).status_code, 422)
        response = self.client.post("/api/auth/register", json={**base, "education_level": "college", "study_group": "К-21"})
        self.assertEqual(response.status_code, 201, response.text)
        headers = {"Authorization": f"Bearer {response.json()['token']}"}
        updated = self.client.patch("/api/me", headers=headers, json={"name": "Новый студент", "education_level": "university", "study_group": "ИС-23", "contact": "", "bio": ""})
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["education_level"], "university")
        self.assertEqual(updated.json()["study_group"], "ИС-23")

    def test_telegram_support_routes_question_and_reply(self):
        bot = SimpleNamespace(send_message=AsyncMock(return_value=SimpleNamespace(message_id=98765)))
        state = SimpleNamespace(set_state=AsyncMock())
        start_message = SimpleNamespace(text="/start support", chat=SimpleNamespace(id=1234, type="private"), answer=AsyncMock())
        user_message = SimpleNamespace(text="Как удалить объявление?", from_user=SimpleNamespace(full_name="Алия", username="aliya"), chat=SimpleNamespace(id=1234), bot=bot, answer=AsyncMock())
        admin_reply = SimpleNamespace(text="Откройте карточку и нажмите удалить.", chat=SimpleNamespace(id=9999), reply_to_message=SimpleNamespace(message_id=98765), bot=bot, answer=AsyncMock(), reply=AsyncMock())
        with patch("app.main.SUPPORT_CHAT_ID", "9999"):
            asyncio.run(bot_start(start_message, state))
            state.set_state.assert_awaited_once()
            asyncio.run(bot_support_message(user_message))
            bot.send_message.assert_any_await(9999, unittest.mock.ANY)
            asyncio.run(bot_support_reply(admin_reply))
            bot.send_message.assert_any_await(1234, unittest.mock.ANY)
            admin_reply.reply.assert_awaited_once()

    def test_support_link_requires_bot_and_support_chat(self):
        with patch("app.main.BOT_TOKEN", "test-token"), patch("app.main.BOT_USERNAME", "CuruTestBot"), patch("app.main.SUPPORT_CHAT_ID", "9999"):
            self.assertEqual(self.client.get("/api/support").json()["bot_url"], "https://t.me/CuruTestBot?start=support")
        self.assertEqual(self.client.get("/api/support").json()["bot_url"], "")

    def test_bot_categories_work_without_site_account_and_survive_linking(self):
        chat = SimpleNamespace(id=888001, type="private")
        message = SimpleNamespace(text="/start", chat=chat, answer=AsyncMock())
        asyncio.run(bot_start(message, SimpleNamespace()))
        message.answer.assert_awaited_once()
        stale_link = SimpleNamespace(text="/start invalid", chat=chat, answer=AsyncMock())
        asyncio.run(bot_start(stale_link, SimpleNamespace()))
        self.assertIn("reply_markup", stale_link.answer.await_args.kwargs)
        with SessionLocal() as db:
            sub = db.query(TelegramSubscription).filter_by(chat_id=str(chat.id)).one()
            self.assertEqual(sub.categories, "")
        callback = SimpleNamespace(data="cat:2", message=SimpleNamespace(chat=chat, edit_reply_markup=AsyncMock()), answer=AsyncMock())
        asyncio.run(bot_preference(callback))
        with SessionLocal() as db:
            sub = db.query(TelegramSubscription).filter_by(chat_id=str(chat.id)).one()
            self.assertEqual(sub.categories, "Книги")
        categories_message = SimpleNamespace(chat=chat, answer=AsyncMock())
        asyncio.run(bot_categories(categories_message))
        self.assertIn("✅ Книги", [row[0].text for row in categories_message.answer.await_args.kwargs["reply_markup"].inline_keyboard])

        owner = self.client.post("/api/auth/register", json={"name": "Автор уведомления", "email": "notify-owner@example.com", "password": "password123", "education_level": "university", "contact": "@owner"}).json()
        headers = {"Authorization": f"Bearer {owner['token']}"}
        listing = self.client.post("/api/listings", headers=headers, json={"title": "Книга для бота", "description": "Полезная книга для учёбы", "category": "Книги", "condition": "Хорошее состояние", "location": "Библиотека"}).json()
        fake_bot = SimpleNamespace(send_message=AsyncMock(), session=SimpleNamespace(close=AsyncMock()))
        with patch("app.main.BOT_TOKEN", "test-token"), patch("app.main.Bot", return_value=fake_bot):
            asyncio.run(notify_subscribers(listing["id"]))
        fake_bot.send_message.assert_awaited_once()
        self.assertEqual(fake_bot.send_message.await_args.args[0], str(chat.id))

        linked_message = SimpleNamespace(text=f"/start {telegram_code(owner['user']['id'])}", chat=chat, answer=AsyncMock())
        asyncio.run(bot_start(linked_message, SimpleNamespace()))
        with SessionLocal() as db:
            self.assertIsNone(db.query(TelegramSubscription).filter_by(chat_id=str(chat.id)).first())
            self.assertEqual(db.query(Subscription).filter_by(chat_id=str(chat.id)).one().categories, "Книги")
        self.assertEqual(self.client.delete(f"/api/listings/{listing['id']}", headers=headers).status_code, 204)


if __name__ == "__main__":
    unittest.main()
