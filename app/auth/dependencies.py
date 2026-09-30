from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

import services
from app.auth.security import decode_jwt
from app.db.session import get_db
from app.models import User


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/token")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = decode_jwt(token)
        subject = payload.get("sub")
        if not isinstance(subject, str) or not subject.isdigit():
            raise ValueError("Invalid token subject")
        user = services.get_user(db, int(subject))
        if user is None:
            raise ValueError("User does not exist")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
