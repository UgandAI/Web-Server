from datetime import datetime, timezone
import logging
from typing import Optional
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import schemas
from app.auth.dependencies import get_current_user
from app.auth.security import encode_jwt, verify_password
from app.chat import create_chat_response
from app.core.config import settings
from app.db.session import check_db_connection, get_db
from app.models import User
from services import create_user, get_user_by_username

from app.profiles.router import router as profiles_router
from app.logbook.router import router as logbook_router
from app.recommendations.router import router as recommendations_router

logger = logging.getLogger(__name__)

app = FastAPI(title="UgandAI API", description="UgandAI backend API", version="1.0.0")

app.include_router(profiles_router)
app.include_router(logbook_router)
app.include_router(recommendations_router)


class ChatRequest(BaseModel):
    sender: str = "user"
    content: str


class ChatResponse(BaseModel):
    messageId: str
    sender: str
    content: str
    timestamp: datetime
    thread_id: Optional[str] = None


@app.get("/health", status_code=status.HTTP_200_OK)
def health_check():
    connected = check_db_connection()
    return {"status": "ok", "database": "connected" if connected else "unavailable"}


def _register_user(request: schemas.UserCreate, db: Session):
    if request.username not in settings.VERIFIED_USERS:
        raise HTTPException(400, "Username is not verified for registration.")
    if get_user_by_username(db, request.username):
        raise HTTPException(400, "Username which is already in use.")
    try:
        return create_user(db, request)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(400, "Username or email is already in use.") from exc


@app.post("/users/register", response_model=schemas.User)
@app.post("/users/register/", response_model=schemas.User, include_in_schema=False)
def register(request: schemas.UserCreate, db: Session = Depends(get_db)):
    return _register_user(request, db)


@app.post("/signup", response_model=schemas.SignupUser)
def signup(request: schemas.SignupCreate, db: Session = Depends(get_db)):
    return _register_user(request, db)


@app.post("/api/token")
@app.post("/login", include_in_schema=False)
def issue_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = get_user_by_username(db, form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid Username or Password")
    token = encode_jwt({"username": user.username, "password_hash": user.hashed_password})
    return {"access_token": token, "token_type": "bearer"}


from fastapi.responses import StreamingResponse

@app.post("/chats", status_code=status.HTTP_200_OK)
def chat(
    request: ChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        # Pass the generator directly to StreamingResponse
        return StreamingResponse(
            create_chat_response(db, user, request.content),
            media_type="text/event-stream"
        )
    except Exception as exc:
        logger.exception("Chat request failed")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Chat service unavailable") from exc
