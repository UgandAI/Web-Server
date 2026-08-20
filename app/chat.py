import logging

from sqlalchemy.orm import Session

from app.models import Conversation, Message, User
from app.openai_service import ChatModel, OpenAIResponsesService

logger = logging.getLogger(__name__)


def validate_chat_content(content: str) -> None:
    """Run existing validators when their optional Hub packages are usable."""
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
                "buyanga", "mbale", "namutumba",
            ],
            disable_classifier=True,
            disable_llm=False,
            on_fail="exception",
        ),
    )
    guard.validate(content)


def create_conversation(db: Session, user: User) -> Conversation:
    conversation = Conversation(user_id=user.id)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def get_owned_conversation(
    db: Session, user: User, conversation_id: int
) -> Conversation | None:
    return db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == user.id,
    ).first()


def send_message(
    db: Session,
    conversation: Conversation,
    content: str,
    model: ChatModel | None = None,
) -> tuple[Message, Message]:
    validate_chat_content(content)
    user_message = Message(conversation_id=conversation.id, role="user", content=content)
    db.add(user_message)
    db.flush()
    history = [
        {"role": message.role, "content": message.content}
        for message in conversation.messages
    ]
    try:
        response_text = (model or OpenAIResponsesService()).respond(history)
        assistant_message = Message(
            conversation_id=conversation.id, role="assistant", content=response_text
        )
        db.add(assistant_message)
        db.commit()
        db.refresh(user_message)
        db.refresh(assistant_message)
        return user_message, assistant_message
    except Exception:
        db.rollback()
        raise


def get_or_create_conversation(db: Session, user: User) -> Conversation:
    conversation = db.query(Conversation).filter(Conversation.user_id == user.id).first()
    return conversation or create_conversation(db, user)
