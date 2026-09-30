from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from passlib.hash import bcrypt

from app.core.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.verify(password, hashed_password)


def encode_jwt(claims: dict[str, Any]) -> str:
    if not settings.JWT_SECRET:
        raise RuntimeError("JWT_SECRET is required")
    now = datetime.now(timezone.utc)
    payload = {**claims, "iat": now, "exp": now + timedelta(minutes=settings.JWT_TTL_MINUTES)}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_jwt(token: str) -> dict[str, Any]:
    if not settings.JWT_SECRET:
        raise RuntimeError("JWT_SECRET is required")
    return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"], options={"require": ["sub", "iat", "exp"]})
