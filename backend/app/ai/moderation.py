import json
import logging
from models import *
from .moderation_system_prompt import MODERATION_SYSTEM_PROMPT
from .parser import parser_call
from config import config

logger = logging.getLogger(__name__)

async def moderate_listing(listing: ListingIn) -> ModerationResponseModel:
    content: list[ChatCompletionsPart] = [ChatCompletionsTextPart(
        text=json.dumps({
            "title": listing.title,
            "description": listing.description,
            "category": listing.category,
            "condition": listing.condition,
            "location": listing.location,
        }, ensure_ascii=False),
    )]
    if listing.image:
        content.append(ChatCompletionsImagePart(
            image_url=ChatCompletionsImageUrl(
                url=listing.image,
                detail="high",
            )
        ))

    result = await parser_call(
        model=AgnesModel.AGNES_3_FLASH,
        messages=[
            ChatCompletionsMessage(role="system", content=MODERATION_SYSTEM_PROMPT),
            ChatCompletionsMessage(role="user", content=content,)
        ],
        response_format=ModerationResponseModel,
    )

    return result

async def safe_moderate_listing(listing: ListingIn) -> ModerationResponseModel:
    try:
        return await moderate_listing(listing)
    except Exception:
        logger.exception("AI moderation failed; listing requires manual review")
        return ModerationResponseModel(
            decision="review",
            reason="Автоматическая проверка недоступна. Требуется решение администратора.",
        )