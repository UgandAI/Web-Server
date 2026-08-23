from datetime import datetime
from contextlib import asynccontextmanager
import logging

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import schemas
from app.auth.dependencies import get_current_user
from app.auth.security import encode_jwt, verify_password
from app.chat import create_chat_response
from app.core.config import settings, validate_startup_settings
from app.db.session import check_db_connection, get_db
from app.models import Conversation, ConversationMessage, User
from services import create_user, get_user_by_username

from app.profiles.router import router as profiles_router
from app.logbook.router import router as logbook_router
from app.recommendations.router import router as recommendations_router
from app.knowledge.router import router as knowledge_router
from app.voice.router import router as voice_router

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    validate_startup_settings()
    yield


app = FastAPI(
    title="UgandAI API", description="UgandAI backend API", version="1.0.0", lifespan=lifespan
)

app.include_router(profiles_router)
app.include_router(logbook_router)
app.include_router(recommendations_router)
app.include_router(knowledge_router)
app.include_router(voice_router)



class ChatRequest(BaseModel):
    sender: str = "user"
    content: str


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
    token = encode_jwt({"sub": str(user.id), "username": user.username})
    return {"access_token": token, "token_type": "bearer"}


class ConversationSummary(BaseModel):
    id: int
    created_at: datetime
    updated_at: datetime


class MessageSummary(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime


@app.get("/conversations", response_model=list[ConversationSummary])
def list_conversations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Conversation).filter(Conversation.user_id == user.id).order_by(Conversation.id).all()


@app.get("/conversations/{conversation_id}/messages", response_model=list[MessageSummary])
def list_conversation_messages(
    conversation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id, Conversation.user_id == user.id
    ).first()
    if conversation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return conversation.messages


@app.post("/chats", status_code=status.HTTP_200_OK)
def chat(
    request: ChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return StreamingResponse(
            create_chat_response(db, user, request.content),
            media_type="text/event-stream"
        )
    except Exception as exc:
        logger.error("Chat request failed: %s", type(exc).__name__)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Chat service unavailable") from exc
