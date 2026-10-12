from openai import AsyncOpenAI
from pydantic import BaseModel
from typing import TypeVar
from models import AgnesModel, ChatCompletionsMessage
from config import settings

T = TypeVar("T", bound=BaseModel)

def to_openai_b64_format(mime_type: str, b64_json: str) -> str:
    return f"data:{mime_type};base64,{b64_json}"

async def parser_call(
    model: AgnesModel,
    messages: list[ChatCompletionsMessage],
    response_format: type[T],
) -> T:
    client = AsyncOpenAI(
        base_url="https://apihub.agnes-ai.com/v1",
        api_key=settings.mistral_api_key,
    )
    try:
        response = await client.chat.completions.create(
            messages=[message.model_dump(mode="json") for message in messages],
            model=model.value,
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Agnes returned an empty response")
        return response_format.model_validate_json(content)
    finally:
        await client.close()
