import io

from openai import OpenAI

from app.core.config import settings


class OpenAISpeechToText:
    def __init__(self, client=None, model: str | None = None):
        if client is None and not settings.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is required for speech-to-text")
        self.client = client or OpenAI(
            api_key=settings.OPENAI_API_KEY, timeout=settings.OPENAI_TIMEOUT_SECONDS, max_retries=1
        )
        self.model = model or settings.OPENAI_STT_MODEL

    def transcribe(self, audio_bytes: bytes, filename: str = "audio.wav") -> str:
        if not audio_bytes:
            raise ValueError("Audio payload is empty")
        buffer = io.BytesIO(audio_bytes)
        buffer.name = filename
        response = self.client.audio.transcriptions.create(model=self.model, file=buffer)
        text = (response.text or "").strip()
        if not text:
            raise ValueError("Transcription produced no text")
        return text
