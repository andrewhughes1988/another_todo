import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator


HIDDEN_FORMATTING_CHARACTERS = re.compile(r"[\x00-\x1F\x7F\u200B-\u200F\u202A-\u202E\u2060-\u206F\uFEFF]")


def clean_title(value: str) -> str:
    value = HIDDEN_FORMATTING_CHARACTERS.sub("", value)
    return re.sub(r"\s+", " ", value).strip()


def has_meaningful_text(value: str) -> bool:
    return any(character.isalnum() for character in value)


class TodoCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=240)

    @field_validator("title", mode="before")
    @classmethod
    def validate_title(cls, value: str) -> str:
        if not isinstance(value, str):
            return value

        cleaned = clean_title(value)
        if not cleaned:
            raise ValueError("Title is required")

        if not has_meaningful_text(cleaned):
            raise ValueError("Title must include at least one letter or number")

        return cleaned


class TodoUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=240)
    completed: StrictBool | None = None

    @model_validator(mode="after")
    def require_at_least_one_update(self) -> "TodoUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field is required")

        return self

    @field_validator("title", mode="before")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        if value is None:
            return value

        if not isinstance(value, str):
            return value

        cleaned = clean_title(value)
        if not cleaned:
            raise ValueError("Title is required")

        if not has_meaningful_text(cleaned):
            raise ValueError("Title must include at least one letter or number")

        return cleaned


class TodoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    completed: bool
    created_at: datetime
    updated_at: datetime
