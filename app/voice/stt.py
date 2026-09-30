import io
import audioop
import hashlib
import logging
import wave
from dataclasses import dataclass

from openai import OpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AudioDiagnostics:
    duration_seconds: float
    rms: int
    peak: int
    frames: int
    sample_rate: int


def inspect_wav_audio(audio_bytes: bytes) -> AudioDiagnostics | None:
    """Returns PCM measurements for WAV input; other supported formats remain STT-readable."""
    if not audio_bytes.startswith(b"RIFF") or audio_bytes[8:12] != b"WAVE":
        return None
    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as source:
            frames = source.getnframes()
            sample_rate = source.getframerate()
            sample_width = source.getsampwidth()
            pcm = source.readframes(frames)
    except (wave.Error, EOFError) as exc:
        raise ValueError("Invalid WAV audio") from exc
    if frames <= 0 or sample_rate <= 0 or not pcm:
        raise ValueError("Audio payload contains no PCM samples")
    return AudioDiagnostics(
        duration_seconds=frames / sample_rate,
        rms=audioop.rms(pcm, sample_width),
        peak=audioop.max(pcm, sample_width),
        frames=frames,
        sample_rate=sample_rate,
    )


def validate_audio_payload(audio_bytes: bytes) -> AudioDiagnostics | None:
    diagnostics = inspect_wav_audio(audio_bytes)
    if diagnostics is None:
        return None
    if diagnostics.duration_seconds < 0.5:
        raise ValueError("Audio is too short")
    # Emulator evidence: false/silent capture averaged well below 500 RMS; clear speech
    # windows were 1,647-7,148 RMS. This is an audio-evidence gate, not a text filter.
    if diagnostics.rms < 500:
        raise ValueError("Audio is silent or near-silent")
    return diagnostics


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
        audio_hash = hashlib.sha256(audio_bytes).hexdigest()
        logger.info("stt_request file=%s bytes=%d sha256=%s model=%s", filename, len(audio_bytes), audio_hash, self.model)
        # UgandAI currently supports English voice input. Supplying the language avoids
        # occasional incorrect auto-detection (for example English being decoded as Russian).
        response = self.client.audio.transcriptions.create(
            model=self.model,
            file=buffer,
            language="en",
            prompt="Ugandan agriculture, farming, crop and district names. Transcribe natural English accurately.",
            response_format="verbose_json",
        )
        text = (response.text or "").strip()
        raw_response = response.model_dump() if hasattr(response, "model_dump") else vars(response)
        segments = getattr(response, "segments", None) or []
        avg_logprobs = [getattr(item, "avg_logprob", None) for item in segments]
        no_speech_probs = [getattr(item, "no_speech_prob", None) for item in segments]
        logger.warning(
            "stt_raw_response file=%s sha256=%s text=%r avg_logprobs=%r no_speech_probs=%r raw=%r",
            filename, audio_hash, text[:500], avg_logprobs, no_speech_probs, raw_response,
        )
        if not text:
            raise ValueError("Transcription produced no text")
        return text
