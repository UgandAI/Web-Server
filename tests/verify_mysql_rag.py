"""Controlled local-MySQL Week 4 smoke test; never calls OpenAI."""
import json
from pathlib import Path

from app.db.session import SessionLocal
from app.knowledge.ingestion import ingest_document
from app.knowledge.retrieval import KnowledgeRetriever
from app.models import Chunk, Document


class ControlledEmbeddings:
    def embed(self, texts):
        return [
            [1.0, 0.0] if any(word in text.lower() for word in ("maize", "rain", "weed")) else [0.0, 1.0]
            for text in texts
        ]


def main() -> None:
    fixture = Path(__file__).parent / "fixtures" / "uganda_maize_public_domain.txt"
    service = ControlledEmbeddings()
    with SessionLocal() as db:
        db.query(Chunk).delete()
        db.query(Document).delete()
        db.commit()
        first = ingest_document(
            db, title="Uganda Maize Growing Notes", source_identifier="fixture:uganda-maize-notes",
            text=fixture.read_text(encoding="utf-8"), source_type="fixture", embedding_service=service,
        )
        duplicate = ingest_document(
            db, title="Duplicate", source_identifier="fixture:duplicate",
            text=fixture.read_text(encoding="utf-8"), source_type="fixture", embedding_service=service,
        )
        retriever = KnowledgeRetriever(service, top_k=3, threshold=0.25)
        relevant = retriever.retrieve(db, "When should I plant maize after rain?")
        unrelated = retriever.retrieve(db, "How do I repair a motorcycle engine?")
        assert first.created and not duplicate.created
        assert relevant and relevant[0].chunk.document_id == first.document.id
        assert unrelated == []
        print(json.dumps({
            "documents": db.query(Document).count(), "chunks": db.query(Chunk).count(),
            "relevant_chunk_ids": [item.chunk.id for item in relevant],
            "unrelated_results": len(unrelated), "citation": relevant[0].citation(),
        }, sort_keys=True))


if __name__ == "__main__":
    main()
