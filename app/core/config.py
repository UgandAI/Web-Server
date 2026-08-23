import os

from dotenv import load_dotenv


load_dotenv()


class Settings:
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./database.db")
    JWT_SECRET = os.getenv("JWT_SECRET")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL")
    OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    KNOWLEDGE_TOP_K = int(os.getenv("KNOWLEDGE_TOP_K", "3"))
    KNOWLEDGE_SIMILARITY_THRESHOLD = float(os.getenv("KNOWLEDGE_SIMILARITY_THRESHOLD", "0.25"))
    KNOWLEDGE_INGESTION_DIR = os.getenv("KNOWLEDGE_INGESTION_DIR", "./knowledge_sources")
    OPENAI_STT_MODEL = os.getenv("OPENAI_STT_MODEL", "whisper-1")
    OPENAI_TTS_MODEL = os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
    OPENAI_TTS_VOICE = os.getenv("OPENAI_TTS_VOICE", "alloy")
    OPENAI_TIMEOUT_SECONDS = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "30"))
    JWT_TTL_MINUTES = int(os.getenv("JWT_TTL_MINUTES", "1440"))
    VOICE_MAX_UPLOAD_BYTES = int(os.getenv("VOICE_MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
    VERIFIED_USERS = {
        username.strip()
        for username in os.getenv("VERIFIED_USERS", "").split(",")
        if username.strip()
    }


settings = Settings()


def validate_startup_settings() -> None:
    errors = []
    if not settings.DATABASE_URL:
        errors.append("DATABASE_URL is required")
    if not settings.JWT_SECRET or len(settings.JWT_SECRET) < 32:
        errors.append("JWT_SECRET must contain at least 32 characters")
    if not settings.OPENAI_API_KEY:
        errors.append("OPENAI_API_KEY is required")
    if not settings.OPENAI_MODEL:
        errors.append("OPENAI_MODEL is required")
    if settings.OPENAI_TIMEOUT_SECONDS <= 0:
        errors.append("OPENAI_TIMEOUT_SECONDS must be positive")
    if errors:
        raise RuntimeError("Invalid configuration: " + "; ".join(errors))
