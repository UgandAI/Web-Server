from pathlib import Path
import tempfile
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.knowledge.worker import run_ingestion_sweep
from app.models import Chunk, Document, IngestionRun  # noqa: F401


class FakeEmbeddingService:
    def embed(self, texts):
        return [[1.0, 0.0] for _ in texts]


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.temp_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp_directory.name)

    def tearDown(self):
        self.engine.dispose()
        self.temp_directory.cleanup()

    def test_sweep_ingests_new_files_and_skips_duplicates(self):
        (self.directory / "maize.txt").write_text("Plant maize after reliable rains.", encoding="utf-8")
        (self.directory / "beans.txt").write_text("Space bean rows about thirty centimeters apart.", encoding="utf-8")
        with self.Session() as db:
            run = run_ingestion_sweep(db, directory=self.directory, embedding_service=FakeEmbeddingService())
            self.assertEqual(run.status, "success")
            self.assertEqual(run.files_scanned, 2)
            self.assertEqual(run.documents_created, 2)
            self.assertEqual(run.documents_skipped, 0)
            self.assertEqual(db.query(Document).count(), 2)

            second_run = run_ingestion_sweep(db, directory=self.directory, embedding_service=FakeEmbeddingService())
            self.assertEqual(second_run.status, "success")
            self.assertEqual(second_run.documents_created, 0)
            self.assertEqual(second_run.documents_skipped, 2)
            self.assertEqual(db.query(Document).count(), 2)
            self.assertEqual(db.query(IngestionRun).count(), 2)

    def test_sweep_records_per_file_errors_without_failing_whole_run(self):
        (self.directory / "empty.txt").write_text("   ", encoding="utf-8")
        (self.directory / "maize.txt").write_text("Plant maize after reliable rains.", encoding="utf-8")
        with self.Session() as db:
            run = run_ingestion_sweep(db, directory=self.directory, embedding_service=FakeEmbeddingService())
            self.assertEqual(run.status, "completed_with_errors")
            self.assertEqual(run.documents_created, 1)
            self.assertIn("empty.txt", run.error_message)

    def test_sweep_with_missing_directory_records_zero_files(self):
        with self.Session() as db:
            run = run_ingestion_sweep(db, directory=self.directory / "missing", embedding_service=FakeEmbeddingService())
            self.assertEqual(run.status, "success")
            self.assertEqual(run.files_scanned, 0)


if __name__ == "__main__":
    unittest.main()
