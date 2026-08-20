from typing import Protocol

from openai import OpenAI

from app.core.config import settings


class ChatModel(Protocol):
    def respond(self, messages: list[dict[str, str]]) -> str: ...


class OpenAIResponsesService:
    """The single boundary between UgandAI chat and the OpenAI SDK."""

    def __init__(self) -> None:
        if not settings.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is required for chat")
        if not settings.OPENAI_MODEL:
            raise RuntimeError("OPENAI_MODEL is required for chat")
        self._client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def respond(self, messages: list[dict[str, str]]) -> str:
        response = self._client.responses.create(
            model=settings.OPENAI_MODEL, input=messages, store=False
        )
        if not response.output_text:
            raise RuntimeError("OpenAI returned no text response")
        return response.output_text
