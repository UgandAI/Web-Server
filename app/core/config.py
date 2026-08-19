import os

from dotenv import load_dotenv


load_dotenv()


class Settings:
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./database.db")
    JWT_SECRET = os.getenv("JWT_SECRET")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL")
    VERIFIED_USERS = {
        username.strip()
        for username in os.getenv("VERIFIED_USERS", "").split(",")
        if username.strip()
    }


settings = Settings()
