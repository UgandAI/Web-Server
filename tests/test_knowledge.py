import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.knowledge.chunking import chunk_text, normalize_text
from app.knowledge.embeddings import deserialize_embedding, serialize_embedding
from app.knowledge.ingestion import ingest_document
from app.knowledge.retrieval import KnowledgeRetriever, cosine_similarity
from app.models import Chunk, Document  # noqa: F401


class FakeEmbeddingService:
    def __init__(self, mapping=None):
        self.mapping = mapping or {}
        self.calls = 0

    def embed(self, texts):
        self.calls += 1
        return [self.mapping.get(text, [1.0, 0.0]) for text in texts]


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def tearDown(self):
        self.engine.dispose()

    def test_chunking_is_stable_and_overlapping(self):
        text = "  one  two three four five six seven eight nine ten  "
        self.assertEqual(normalize_text(text), "one two three four five six seven eight nine ten")
        self.assertEqual(chunk_text(text, max_words=5, overlap_words=2), [
            "one two three four five", "four five six seven eight", "seven eight nine ten",
        ])
        self.assertEqual(chunk_text("  \n "), [])

    def test_embedding_serialization_round_trip_and_validation(self):
        encoded = serialize_embedding([0, 1.25, -2])
        self.assertEqual(deserialize_embedding(encoded), [0.0, 1.25, -2.0])
        with self.assertRaises(ValueError):
            deserialize_embedding("not-json")

    def test_cosine_similarity(self):
        self.assertAlmostEqual(cosine_similarity([1, 0], [1, 0]), 1.0)
        self.assertAlmostEqual(cosine_similarity([1, 0], [0, 1]), 0.0)
        self.assertAlmostEqual(cosine_similarity([1, 1], [1, 0]), 2 ** -0.5)

    def test_ingestion_creates_document_chunks_and_deduplicates(self):
        service = FakeEmbeddingService()
        with self.Session() as db:
            first = ingest_document(
                db, title="Maize notes", source_identifier="fixture:maize",
                text="Plant maize after reliable rains. Weed the field early.", embedding_service=service,
            )
            second = ingest_document(
                db, title="Duplicate", source_identifier="fixture:copy",
                text=" Plant maize after reliable rains. Weed the field early. ", embedding_service=service,
            )
            self.assertTrue(first.created)
            self.assertFalse(second.created)
            self.assertEqual(first.document.id, second.document.id)
            self.assertEqual(db.query(Document).count(), 1)
            self.assertEqual(db.query(Chunk).count(), 1)
            self.assertEqual(service.calls, 1)

    def test_top_k_and_irrelevant_query(self):
        with self.Session() as db:
            document = Document(title="Notes", source_identifier="fixture", source_type="fixture", checksum="b" * 64)
            db.add(document)
            db.flush()
            db.add_all([
                Chunk(document_id=document.id, chunk_index=0, text="best", embedding=serialize_embedding([1, 0])),
                Chunk(document_id=document.id, chunk_index=1, text="second", embedding=serialize_embedding([0.8, 0.2])),
                Chunk(document_id=document.id, chunk_index=2, text="irrelevant", embedding=serialize_embedding([0, 1])),
                Chunk(document_id=document.id, chunk_index=3, text="malformed", embedding="bad"),
            ])
            db.commit()
            relevant = KnowledgeRetriever(FakeEmbeddingService(), top_k=2, threshold=0.5).retrieve(db, "maize")
            self.assertEqual([item.chunk.text for item in relevant], ["best", "second"])
            irrelevant_service = FakeEmbeddingService({"unrelated": [-1, 0]})
            irrelevant = KnowledgeRetriever(irrelevant_service, top_k=3, threshold=0.25).retrieve(db, "unrelated")
            self.assertEqual(irrelevant, [])


if __name__ == "__main__":
    unittest.main()
