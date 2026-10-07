import os
import tempfile
import unittest

from fastapi.testclient import TestClient

test_dir = tempfile.TemporaryDirectory()
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(test_dir.name, "curu-test.db").replace("\\", "/")
os.environ["SEED_DEMO"] = "false"
os.environ["BOT_TOKEN"] = ""
os.environ["JWT_SECRET"] = "test-secret-with-at-least-thirty-two-characters"

from app.main import app, engine, telegram_code, user_from_telegram_code  # noqa: E402


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
        response = self.client.post("/api/auth/register", json={"name": "Алия Тест", "email": "aliya@example.com", "password": "password123", "faculty": "Инженерия", "contact": "@aliya"})
        self.assertEqual(response.status_code, 201, response.text)
        token = response.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        self.assertEqual(self.client.post("/api/auth/register", json={"name": "Алия Тест", "email": "aliya@example.com", "password": "password123"}).status_code, 409)
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


if __name__ == "__main__":
    unittest.main()
