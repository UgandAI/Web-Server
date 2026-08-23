import math
from dataclasses import dataclass

from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.knowledge.embeddings import OpenAIEmbeddingService, deserialize_embedding
from app.models.knowledge import Chunk


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: Chunk
    score: float

    def citation(self) -> dict:
        document = self.chunk.document
        return {
            "document_id": document.id,
            "title": document.title,
            "source": document.source_identifier,
            "url": document.source_url,
            "chunk_id": self.chunk.id,
            "chunk_index": self.chunk.chunk_index,
        }


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or len(left) != len(right):
        raise ValueError("Embeddings must have equal non-zero dimensions")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return sum(a * b for a, b in zip(left, right)) / (left_norm * right_norm)


class KnowledgeRetriever:
    def __init__(self, embedding_service=None, top_k: int | None = None, threshold: float | None = None):
        self.embedding_service = embedding_service or OpenAIEmbeddingService()
        self.top_k = top_k if top_k is not None else settings.KNOWLEDGE_TOP_K
        self.threshold = threshold if threshold is not None else settings.KNOWLEDGE_SIMILARITY_THRESHOLD

    def retrieve(self, db: Session, query: str) -> list[RetrievedChunk]:
        query_vector = self.embedding_service.embed([query])[0]
        candidates = db.query(Chunk).options(joinedload(Chunk.document)).all()
        scored = []
        for chunk in candidates:
            try:
                vector = deserialize_embedding(chunk.embedding)
                score = cosine_similarity(query_vector, vector)
            except ValueError:
                continue
            if score >= self.threshold:
                scored.append(RetrievedChunk(chunk, score))
        scored.sort(key=lambda item: (-item.score, item.chunk.id))
        return scored[: self.top_k]
