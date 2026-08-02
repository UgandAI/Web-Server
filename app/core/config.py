import os

from dotenv import load_dotenv


load_dotenv()


class Settings:
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./database.db")
    JWT_SECRET = os.getenv("JWT_SECRET", "myjwtsecret")


settings = Settings()
