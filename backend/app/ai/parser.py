from openai import AsyncOpenAI
from pydantic import BaseModel
from typing import TypeVar
from models import ChatCompletionsMessage, MistralModel
from config import settings

T = TypeVar("T", bound=BaseModel)

client = AsyncOpenAI(
    base_url="https://api.mistral.ai/v1",
    api_key=settings.mistral_api_key,
)

def to_openai_b64_format(mime_type: str, b64_json: str) -> str:
    return f"data:{mime_type};base64,{b64_json}"

async def parser_call(
    model: MistralModel,
    messages: list[ChatCompletionsMessage],
    response_format: type[T],
) -> T:
    response = await client.chat.completions.parse(
        messages=[message.model_dump(mode="json") for message in messages], # type: ignore
        model=model.value,
        response_format=response_format,
    )
    message = response.choices[0].message

    if message.parsed is None:
        raise RuntimeError("OpenAI SDK returned none when a valid parsed model expected")

    return message.parsed