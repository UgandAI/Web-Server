from typing import Any

import jwt
from passlib.hash import bcrypt

from app.core.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.verify(password, hashed_password)


def encode_jwt(claims: dict[str, Any]) -> str:
    return jwt.encode(claims, settings.JWT_SECRET)


def decode_jwt(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
