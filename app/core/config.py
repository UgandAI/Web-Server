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
    VERIFIED_USERS = {
        username.strip()
        for username in os.getenv("VERIFIED_USERS", "").split(",")
        if username.strip()
    }


settings = Settings()
