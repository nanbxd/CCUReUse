from openai import AsyncOpenAI
from pydantic import BaseModel
from typing import TypeVar, Literal
from models import AgnesModel, ChatCompletionsMessage, LLMModel, MistralModel
from config import settings

T = TypeVar("T", bound=BaseModel)

clients: dict[Literal["agnes", "mistral"], AsyncOpenAI] = dict()

if settings.agnes_api_key:
    clients["agnes"] = AsyncOpenAI(
        base_url="https://apihub.agnes-ai.com/v1",
        api_key=settings.agnes_api_key,
        timeout=60,
        max_retries=1,
    )

if settings.mistral_api_key:
    clients["mistral"] = AsyncOpenAI(
        base_url="https://api.mistral.ai/v1",
        api_key=settings.mistral_api_key,
        timeout=60,
        max_retries=1,
    )

async def parser_call(
    model: LLMModel,
    messages: list[ChatCompletionsMessage],
    response_format: type[T],
) -> T:
    match model:
        case AgnesModel():
            client = clients.get("agnes")
        case MistralModel():
            client = clients.get("mistral")

    if client is None:
        raise RuntimeError("No available client for this model. Set up the api key to use it.")
    
    response = await client.chat.completions.parse(
        messages=[message.model_dump(mode="json") for message in messages], # type: ignore
        model=model.value,
        response_format=response_format,
        temperature=0.2,
    )
    message = response.choices[0].message

    if message.parsed is None:
        raise RuntimeError("The provider returned none parsed content")

    return message.parsed
