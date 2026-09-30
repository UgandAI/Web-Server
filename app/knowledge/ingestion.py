import hashlib
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.knowledge.chunking import chunk_text, normalize_text
from app.knowledge.embeddings import OpenAIEmbeddingService, serialize_embedding
from app.models.knowledge import Chunk, Document


@dataclass(frozen=True)
class IngestionResult:
    document: Document
    created: bool


def content_checksum(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def ingest_document(
    db: Session,
    *,
    title: str,
    source_identifier: str,
    text: str,
    source_url: str | None = None,
    source_type: str = "local",
    published_at: datetime | None = None,
    embedding_service=None,
    commit: bool = True,
) -> IngestionResult:
    normalized = normalize_text(text)
    if not normalized:
        raise ValueError("Document text is empty")
    checksum = content_checksum(normalized)
    existing = db.query(Document).filter(Document.checksum == checksum).first()
    if existing:
        return IngestionResult(existing, False)

    pieces = chunk_text(normalized)
    service = embedding_service or OpenAIEmbeddingService()
    vectors = service.embed(pieces)
    if len(vectors) != len(pieces):
        raise RuntimeError("One embedding is required for every chunk")

    document = Document(
        title=title.strip(), source_identifier=source_identifier.strip(), source_url=source_url,
        source_type=source_type, checksum=checksum, published_at=published_at,
    )
    try:
        db.add(document)
        db.flush()
        for index, (piece, vector) in enumerate(zip(pieces, vectors)):
            db.add(Chunk(
                document_id=document.id, chunk_index=index, text=piece,
                embedding=serialize_embedding(vector), token_count=len(piece.split()),
            ))
        if commit:
            db.commit()
            db.refresh(document)
        else:
            db.flush()
    except Exception:
        if commit:
            db.rollback()
        raise
    return IngestionResult(document, True)
