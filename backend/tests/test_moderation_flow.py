import asyncio
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from fastapi.testclient import TestClient

test_directory = tempfile.TemporaryDirectory()
os.environ.update({
    "DATABASE_URL": "sqlite:///" + os.path.join(test_directory.name, "moderation.db").replace("\\", "/"),
    "JWT_SECRET": "test-secret-long-enough-for-local-moderation-tests",
    "SEED_DEMO": "false",
    "BOT_TOKEN": "",
    "ADMIN_PASSWORD": "test-admin-password",
    "MISTRAL_API_KEY": "test-agnes-key",
    "SUPPORT_CHAT_ID": "12345",
})

from app.main import app, engine  # noqa: E402
from app.bot import bot_moderate_listing  # noqa: E402
from app.ai.moderation import moderate_listing, safe_moderate_listing  # noqa: E402
from aiogram.types import Message  # noqa: E402
from config import settings  # noqa: E402
from models import ListingIn, ModerationResponseModel  # noqa: E402


class ModerationFlowTest(unittest.TestCase):
    def test_agnes_receives_text_and_image(self) -> None:
        client = Mock()
        client.chat.completions.create = AsyncMock(return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"decision":"approve","reason":"Book matches photo","advice":null}'))],
        ))
        client.close = AsyncMock()
        with patch("app.ai.moderation.AsyncOpenAI", return_value=client) as sdk:
            result = asyncio.run(moderate_listing(ListingIn(
                title="Study book", description="A physical book for students",
                category="Книги", condition="Good", location="Library",
                image="data:image/png;base64,aGVsbG8=",
            )))
        self.assertEqual(result.decision, "approve")
        self.assertEqual(sdk.call_args.kwargs["base_url"], "https://apihub.agnes-ai.com/v1")
        request = client.chat.completions.create.await_args.kwargs
        self.assertEqual(request["model"], "agnes-2.5-flash")
        self.assertEqual(request["messages"][1]["content"][1]["type"], "image_url")

    def test_agnes_failure_requires_manual_review(self) -> None:
        with patch("app.ai.moderation.moderate_listing", new_callable=AsyncMock, side_effect=RuntimeError("API unavailable")):
            result = asyncio.run(safe_moderate_listing(ListingIn(
                title="Study book", description="A physical book for students",
                category="Книги", condition="Good", location="Library",
            )))
        self.assertEqual(result.decision, "review")

    @classmethod
    def setUpClass(cls) -> None:
        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()
        response = cls.client.post("/api/auth/register", json={
            "name": "Test User", "email": "moderation@example.com", "password": "password123",
            "education_level": "university", "contact": "@moderation",
        })
        assert response.status_code == 201, response.text
        cls.headers = {"Authorization": "Bearer " + response.json()["token"]}
        admin = cls.client.post("/api/auth/login", json={"email": "demo@curu.local", "password": "test-admin-password"})
        assert admin.status_code == 200, admin.text
        cls.admin_headers = {"Authorization": "Bearer " + admin.json()["token"]}

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client_context.__exit__(None, None, None)
        engine.dispose()
        test_directory.cleanup()

    def create(self, decision: str) -> dict:
        result = ModerationResponseModel(
            decision=decision,
            reason="Image does not match the listing" if decision != "approve" else "Clear item",
            advice="Use a matching photo" if decision == "reject" else None,
        )
        payload = {
            "title": "Study book", "description": "A physical book for students",
            "category": "Книги", "condition": "Good", "location": "Library", "image": "",
        }
        with patch.object(settings, "bot_token", "123456:FAKE"), \
             patch("app.main.safe_moderate_listing", new_callable=AsyncMock, return_value=result), \
             patch("app.main.notify_admin_for_review", new_callable=AsyncMock) as notify_admin, \
             patch("app.main.notify_subscribers", new_callable=AsyncMock) as notify_subscribers:
            response = self.client.post("/api/listings", headers=self.headers, json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        if decision == "approve":
            notify_subscribers.assert_awaited_once()
            notify_admin.assert_not_awaited()
        else:
            notify_admin.assert_awaited_once()
            notify_subscribers.assert_not_awaited()
        return response.json()

    def test_rejected_listing_stays_private_until_approved(self) -> None:
        item = self.create("reject")
        listing_id = item["id"]
        self.assertEqual(item["status"], "pending")
        self.assertEqual(self.client.get(f"/api/listings/{listing_id}").status_code, 404)
        self.assertEqual(self.client.get(f"/api/listings/{listing_id}", headers=self.headers).status_code, 200)
        self.assertEqual(self.client.get("/api/listings?status=all").json(), [])
        self.assertEqual(self.client.patch(f"/api/listings/{listing_id}/status", headers=self.headers, json={"status": "available"}).status_code, 409)
        with patch("app.main.notify_subscribers", new_callable=AsyncMock):
            approved = self.client.post(f"/api/admin/listings/{listing_id}/approve", headers=self.admin_headers)
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertEqual(approved.json()["status"], "available")
        self.assertEqual(self.client.get(f"/api/listings/{listing_id}").status_code, 200)

    def test_review_listing_can_be_deleted(self) -> None:
        item = self.create("review")
        listing_id = item["id"]
        self.assertEqual(self.client.post(f"/api/admin/listings/{listing_id}/approve", headers=self.headers).status_code, 403)
        self.assertEqual(self.client.delete(f"/api/listings/{listing_id}", headers=self.admin_headers).status_code, 204)
        self.assertEqual(self.client.get(f"/api/listings/{listing_id}", headers=self.headers).status_code, 404)

    def test_missing_agnes_key_prevents_publication(self) -> None:
        with patch.object(settings, "mistral_api_key", ""), patch.object(settings, "bot_token", "123456:FAKE"):
            response = self.client.post("/api/listings", headers=self.headers, json={
                "title": "Study book", "description": "A physical book for students",
                "category": "Книги", "condition": "Good", "location": "Library",
            })
        self.assertEqual(response.status_code, 503)

    def test_telegram_buttons_restrict_admin_and_publish(self) -> None:
        item = self.create("reject")
        message = Mock(spec=Message)
        message.chat = SimpleNamespace(id=12345, type="private")
        message.edit_reply_markup = AsyncMock()
        callback = SimpleNamespace(
            message=message, bot=Mock(), data=f"moderate:approve:{item['id']}",
            answer=AsyncMock(), from_user=SimpleNamespace(id=99999),
        )
        asyncio.run(bot_moderate_listing(callback))
        self.assertEqual(self.client.get(f"/api/listings/{item['id']}").status_code, 404)
        callback.from_user.id = 12345
        with patch("app.main.notify_subscribers", new_callable=AsyncMock) as notify_subscribers:
            asyncio.run(bot_moderate_listing(callback))
        self.assertEqual(self.client.get(f"/api/listings/{item['id']}").status_code, 200)
        notify_subscribers.assert_awaited_once_with(item["id"])


if __name__ == "__main__":
    unittest.main()
