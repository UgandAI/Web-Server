from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session, joinedload

from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models import Chunk, Citation, Conversation, ConversationMessage, Document, IngestionRun, User

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


class DocumentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    source_identifier: str
    source_url: str | None
    source_type: str
    published_at: datetime | None
    created_at: datetime


class ChunkSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    document_id: int
    chunk_index: int
    text: str
    token_count: int | None
    created_at: datetime


class CitationSummary(BaseModel):
    chunk_id: int
    document_id: int
    title: str
    source: str
    url: str | None
    chunk_index: int
    score: float


class IngestionRunSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    started_at: datetime
    finished_at: datetime | None
    status: str
    source_directory: str
    files_scanned: int
    documents_created: int
    documents_skipped: int
    chunks_created: int
    error_message: str | None


@router.get("/documents", response_model=list[DocumentSummary])
def list_documents(
    _user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return db.query(Document).order_by(Document.created_at.desc(), Document.id.desc()).limit(100).all()


@router.get("/documents/{document_id}/chunks", response_model=list[ChunkSummary])
def list_document_chunks(
    document_id: int, _user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(404, "Document not found")
    return db.query(Chunk).filter(Chunk.document_id == document_id).order_by(Chunk.chunk_index).all()


@router.get("/messages/{message_id}/citations", response_model=list[CitationSummary])
def list_message_citations(
    message_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    message = (
        db.query(ConversationMessage)
        .join(Conversation, Conversation.id == ConversationMessage.conversation_id)
        .filter(ConversationMessage.id == message_id, Conversation.user_id == user.id)
        .first()
    )
    if message is None:
        raise HTTPException(404, "Message not found")
    citations = (
        db.query(Citation)
        .options(joinedload(Citation.chunk).joinedload(Chunk.document))
        .filter(Citation.message_id == message_id)
        .order_by(Citation.score.desc())
        .all()
    )
    return [
        CitationSummary(
            chunk_id=citation.chunk.id,
            document_id=citation.chunk.document.id,
            title=citation.chunk.document.title,
            source=citation.chunk.document.source_identifier,
            url=citation.chunk.document.source_url,
            chunk_index=citation.chunk.chunk_index,
            score=citation.score,
        )
        for citation in citations
    ]


@router.get("/ingestion-runs", response_model=list[IngestionRunSummary])
def list_ingestion_runs(
    _user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return db.query(IngestionRun).order_by(IngestionRun.started_at.desc()).limit(50).all()
