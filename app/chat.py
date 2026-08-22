import logging
import json

from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Conversation, ConversationMessage, User

logger = logging.getLogger(__name__)


def validate_chat_content(content: str) -> None:
    """Run the existing validators when their optional Hub packages are usable."""
    try:
        from guardrails import Guard
        from guardrails.hub import NSFWText, RestrictToTopic
    except (ImportError, RuntimeError) as exc:
        logger.warning("Guardrails validators unavailable: %s", exc)
        return

    guard = Guard().use_many(
        NSFWText(threshold=0.8, validation_method="sentence", on_fail="exception"),
        RestrictToTopic(
            valid_topics=[
                "uganda", "farm", "farming", "planting", "crops", "plant",
                "buyanga", "mbale", "namutumba"
            ],
            disable_classifier=True,
            disable_llm=False,
            on_fail="exception",
        ),
    )
    guard.validate(content)


def create_chat_response(db: Session, user: User, content: str) -> str:
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is required for chat")
    if not settings.OPENAI_MODEL:
        raise RuntimeError("OPENAI_MODEL is required for chat")

    try:
        validate_chat_content(content)
    except Exception as exc:
        return str(exc)
    conversation = db.query(Conversation).filter(Conversation.user_id == user.id).first()
    if conversation is None:
        conversation = Conversation(user_id=user.id)
        db.add(conversation)
        db.flush()

    db.add(ConversationMessage(
        conversation_id=conversation.id, role="user", content=content
    ))
    db.flush()
    history = [
        {"role": message.role, "content": message.content}
        for message in conversation.messages
    ]

    try:
        # Include SYSTEM_PROMPT in history
        history.insert(0, {"role": "system", "content": getattr(settings, 'SYSTEM_PROMPT', "You are a helpful assistant")})
        
        response = OpenAI(api_key=settings.OPENAI_API_KEY).chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=history,
            stream=True,
        )
        
        full_response = ""
        for chunk in response:
            if chunk.choices[0].delta.content:
                text_chunk = chunk.choices[0].delta.content
                full_response += text_chunk
                yield f"data: {json.dumps({'content': text_chunk})}\n\n"
        
        db.add(ConversationMessage(
            conversation_id=conversation.id, role="assistant", content=full_response
        ))
        db.commit()
        
    except Exception as exc:
        db.rollback()
        logger.exception("Streaming chat failed")
        yield f"data: {json.dumps({'error': str(exc)})}\n\n"
