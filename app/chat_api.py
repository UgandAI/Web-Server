from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.chat import create_conversation, get_owned_conversation, send_message
from app.db.session import get_db
from app.models import User

router = APIRouter(prefix="/conversations", tags=["chat"])


class ConversationResponse(BaseModel):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=20_000)


class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    role: str
    content: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class MessageExchangeResponse(BaseModel):
    user_message: MessageResponse
    assistant_message: MessageResponse


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
def start_conversation(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return create_conversation(db, user)


def require_conversation(conversation_id: int, user: User, db: Session):
    conversation = get_owned_conversation(db, user, conversation_id)
    if conversation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return conversation


@router.post("/{conversation_id}/messages", response_model=MessageExchangeResponse, status_code=201)
def post_message(
    conversation_id: int,
    request: SendMessageRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = require_conversation(conversation_id, user, db)
    try:
        user_message, assistant_message = send_message(db, conversation, request.content)
    except Exception as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Chat service unavailable") from exc
    return MessageExchangeResponse(
        user_message=MessageResponse.model_validate(user_message),
        assistant_message=MessageResponse.model_validate(assistant_message),
    )


@router.get("/{conversation_id}/messages", response_model=list[MessageResponse])
def conversation_history(
    conversation_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return require_conversation(conversation_id, user, db).messages
