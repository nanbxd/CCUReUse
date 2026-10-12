import json
import logging

from openai import AsyncOpenAI

from config import settings
from models import ListingIn, ModerationResponseModel
from .moderation_system_prompt import MODERATION_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


async def moderate_listing(listing: ListingIn) -> ModerationResponseModel:
    """Check the complete listing with Agnes, including its image when present."""
    content: list[dict[str, object]] = [{
        "type": "text",
        "text": json.dumps({
            "title": listing.title,
            "description": listing.description,
            "category": listing.category,
            "condition": listing.condition,
            "location": listing.location,
        }, ensure_ascii=False),
    }]
    if listing.image:
        content.append({"type": "image_url", "image_url": {"url": listing.image}})

    client = AsyncOpenAI(
        api_key=settings.mistral_api_key,
        base_url="https://apihub.agnes-ai.com/v1",
        timeout=30.0,
        max_retries=1,
    )
    try:
        response = await client.chat.completions.create(
            model="agnes-2.5-flash",
            messages=[
                {"role": "system", "content": MODERATION_SYSTEM_PROMPT + "\nReturn only a JSON object with keys decision, reason, advice. Do not use Markdown."},
                {"role": "user", "content": content},
            ],
            stream=False,
        )
        raw = response.choices[0].message.content
        if not raw:
            raise ValueError("Agnes returned an empty moderation response")
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return ModerationResponseModel.model_validate_json(raw)
    finally:
        await client.close()


async def safe_moderate_listing(listing: ListingIn) -> ModerationResponseModel:
    try:
        return await moderate_listing(listing)
    except Exception:
        logger.exception("Agnes moderation failed; listing requires manual review")
        return ModerationResponseModel(
            decision="review",
            reason="Автоматическая проверка недоступна. Требуется решение администратора.",
        )
