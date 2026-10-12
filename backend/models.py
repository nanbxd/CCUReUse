from typing import Literal, TypeAlias
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from config import config
from enum import Enum

class UserIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    education_level: Literal["university", "college"]
    study_group: str = Field(default="", max_length=40)
    contact: str = Field(default="", max_length=200)


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str


class ProfileIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    education_level: Literal["university", "college"] | None = None
    study_group: str = Field(default="", max_length=40)
    contact: str = Field(default="", max_length=200)
    bio: str = Field(default="", max_length=400)


class ListingIn(BaseModel):
    title: str = Field(min_length=3, max_length=100)
    description: str = Field(min_length=10, max_length=2000)
    category: str
    condition: str = Field(min_length=2, max_length=40)
    location: str = Field(min_length=2, max_length=120)
    image: str = Field(default="", max_length=2_800_000)

    @field_validator("category")
    @classmethod
    def category_valid(cls, value: str) -> str:
        if value not in config.categories:
            raise ValueError("Неизвестная категория")
        return value

    @field_validator("image")
    @classmethod
    def image_valid(cls, value: str) -> str:
        if value and not (value.startswith("data:image/jpeg;base64,") or value.startswith("data:image/png;base64,") or value.startswith("data:image/webp;base64,") or value.startswith("https://")):
            raise ValueError("Нужно изображение JPEG, PNG, WebP или HTTPS-ссылка")
        return value


class StatusIn(BaseModel):
    status: Literal["available", "reserved", "given"]


class PreferencesIn(BaseModel):
    categories: list[str]
    enabled: bool = True

    @field_validator("categories")
    @classmethod
    def categories_valid(cls, value: list[str]) -> list[str]:
        if any(category not in config.categories for category in value):
            raise ValueError("Неизвестная категория")
        return list(dict.fromkeys(value))

class ChatCompletionsTextPart(BaseModel):
    type: Literal["text"] = "text"
    text: str

class ChatCompletionsImageUrl(BaseModel):
    url: str
    detail: Literal["auto", "low", "high"] = "auto"

class ChatCompletionsImagePart(BaseModel):
    type: Literal["image_url"] = "image_url"
    type: Literal["image_url"] = "image_url"
    image_url: ChatCompletionsImageUrl

ChatCompletionsPart: TypeAlias = ChatCompletionsTextPart | ChatCompletionsImagePart

class ChatCompletionsMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str | list[ChatCompletionsPart]

class AgnesModel(str, Enum):
    FLASH = "agnes-2.5-flash"

class ModerationResponseModel(BaseModel):
    decision: Literal["approve", "reject", "review"] = Field(
        description=(
            "Whether the listing should be published, rejected, "
            "or sent for manual review. Only approve listings offering "
            "a genuine, identifiable physical item that complies with "
            "all moderation rules. Use review for genuinely ambiguous cases."
        )
    )

    reason: str = Field(
        description=(
            "A brief, one-sentence explanation of the moderation decision "
            "based on the listing content and moderation rules."
        )
    )

    advice: str | None = Field(
        default=None,
        description=(
            "For rejected listings, provide actionable advice on how to "
            "correct the listing so it may comply with the rules, if possible. "
            "For review or approved listings, use null. Never suggest ways "
            "to disguise or bypass a policy violation."
        ),
    )