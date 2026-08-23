import base64
import json
import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.chat import create_chat_response
from app.core.config import settings
from app.db.session import get_db
from app.models import User
from app.voice.stt import OpenAISpeechToText
from app.voice.tts import OpenAITextToSpeech

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])


class VoiceChatResponse(BaseModel):
    transcript: str
    content: str
    citations: list[dict]
    audio_base64: str
    audio_format: str = "mp3"


def get_speech_to_text() -> OpenAISpeechToText:
    return OpenAISpeechToText()


def get_text_to_speech() -> OpenAITextToSpeech:
    return OpenAITextToSpeech()


@router.post("/chat", response_model=VoiceChatResponse)
async def voice_chat(
    audio: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    stt: OpenAISpeechToText = Depends(get_speech_to_text),
    tts: OpenAITextToSpeech = Depends(get_text_to_speech),
):
    """Speech in, speech out: transcribes the upload, runs it through the normal RAG
    chat pipeline, then synthesizes the reply as audio."""
    if not audio.content_type or not audio.content_type.startswith("audio/"):
        raise HTTPException(415, "An audio content type is required")
    audio_bytes = await audio.read(settings.VOICE_MAX_UPLOAD_BYTES + 1)
    if not audio_bytes:
        raise HTTPException(422, "Audio payload is empty")
    if len(audio_bytes) > settings.VOICE_MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Audio payload is too large")
    try:
        transcript = stt.transcribe(audio_bytes, filename=audio.filename or "audio.wav")
    except ValueError as exc:
        raise HTTPException(422, "Audio could not be transcribed") from exc
    except Exception as exc:
        logger.error("Speech transcription failed: %s", type(exc).__name__)
        raise HTTPException(502, "Speech transcription unavailable") from exc

    content = ""
    citations: list[dict] = []
    for event in create_chat_response(db, user, transcript):
        payload = json.loads(event.removeprefix("data: ").strip())
        if "error" in payload:
            raise HTTPException(502, payload["error"])
        if "content" in payload:
            content = payload["content"]
        if "citations" in payload:
            citations = payload["citations"]

    if not content:
        raise HTTPException(502, "Chat service produced no response")

    try:
        reply_audio = tts.synthesize(content)
    except Exception as exc:
        logger.error("Speech synthesis failed: %s", type(exc).__name__)
        raise HTTPException(502, "Speech synthesis unavailable") from exc
    if not reply_audio:
        raise HTTPException(502, "Speech synthesis produced no audio")

    return VoiceChatResponse(
        transcript=transcript,
        content=content,
        citations=citations,
        audio_base64=base64.b64encode(reply_audio).decode("ascii"),
    )
