import json
import logging
from models import *
from .moderation_system_prompt import MODERATION_SYSTEM_PROMPT
from .parser import parser_call
from config import config

logger = logging.getLogger(__name__)

_RUSSIAN_LETTERS = frozenset("АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдеёжзийклмнопрстуфхцчшщъыьэюя")


def _mostly_russian(text: str) -> bool:
    russian_letters = sum(letter in _RUSSIAN_LETTERS for letter in text)
    latin_letters = sum("a" <= letter.lower() <= "z" for letter in text)
    return russian_letters >= 5 and russian_letters > latin_letters


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

    system_prompt = MODERATION_SYSTEM_PROMPT
    # russian_listing = _mostly_russian(f"{listing.title} {listing.description}")
    # if russian_listing:
    #     system_prompt += "\n\nThe title and description are in Russian. Write the reason in Russian, using Cyrillic. Keep JSON keys and decision values unchanged."
        
    messages = [
        ChatCompletionsMessage(role="system", content=system_prompt),
        ChatCompletionsMessage(role="user", content=content),
    ]

    try:
        result = await parser_call(
            model=AgnesModel.AGNES_3_FLASH,
            messages=messages,
            response_format=ModerationResponseModel,
        )
    except Exception:
        result = await parser_call(
            model=MistralModel.MINISTRAL_14B,
            messages=messages,
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
