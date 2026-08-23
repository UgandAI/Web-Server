import os
from pathlib import Path
import subprocess
import sys
import unittest
import json
import tempfile
from unittest.mock import patch


MYSQL_TEST_DATABASE_URL = os.getenv("MYSQL_TEST_DATABASE_URL")


def run_mysql_flow() -> None:
    import guardrails.hub
    from alembic import command
    from alembic.config import Config
    from fastapi.testclient import TestClient

    class _UnavailableHubValidator:
        def __init__(self, *args, **kwargs):
            pass

    guardrails.hub.NSFWText = _UnavailableHubValidator
    guardrails.hub.RestrictToTopic = _UnavailableHubValidator

    os.environ["DATABASE_URL"] = MYSQL_TEST_DATABASE_URL
    os.environ["OPENAI_API_KEY"] = "local-test-placeholder"
    os.environ["OPENAI_MODEL"] = "local-test-model"
    os.environ["JWT_SECRET"] = "local-mysql-test-secret-with-32-bytes"
    os.environ["VERIFIED_USERS"] = "mysql-alice"

    repository_root = Path(__file__).resolve().parents[1]
    command.upgrade(Config(repository_root / "alembic.ini"), "head")

    from app.main import app
    from app.db.session import SessionLocal, engine
    from app.models import Chunk, Citation, Conversation, ConversationMessage, Document, IngestionRun, LogbookEntry, FarmProfile, User
    from app.knowledge.ingestion import ingest_document
    from app.knowledge.retrieval import KnowledgeRetriever
    from app.knowledge.worker import run_ingestion_sweep
    from app.recommendations.router import get_recommendation_service
    from app.voice.router import get_speech_to_text, get_text_to_speech

    class ControlledEmbeddings:
        def embed(self, texts):
            return [[1.0, 0.0] if any(word in text.lower() for word in ("maize", "rain")) else [0.0, 1.0] for text in texts]

    class FakeResponse:
        output_text = "Plant maize after reliable rains."

    class FakeOpenAI:
        def __init__(self, **kwargs):
            class Responses:
                def create(self, **kwargs):
                    return FakeResponse()
            self.responses = Responses()

    class FakeRecommendation:
        def generate(self, **kwargs):
            return "Prepare the field before reliable rains."

    class FakeSTT:
        def transcribe(self, audio_bytes, filename="audio.wav"):
            return "When should I plant maize?"

    class FakeTTS:
        def synthesize(self, text):
            return b"controlled-mp3"

    client = TestClient(app)
    try:
        with SessionLocal() as db:
            db.query(Citation).delete()
            db.query(ConversationMessage).delete()
            db.query(Conversation).delete()
            db.query(LogbookEntry).delete()
            db.query(FarmProfile).delete()
            db.query(Chunk).delete()
            db.query(Document).delete()
            db.query(IngestionRun).delete()
            db.query(User).filter(User.username == "mysql-alice").delete()
            db.commit()

        signup = client.post(
            "/signup",
            json={
                "username": "mysql-alice",
                "email": "mysql-alice@example.test",
                "password": "correct-password",
            },
        )
        assert signup.status_code == 200, signup.text

        login = client.post(
            "/login",
            data={
                "username": "mysql-alice",
                "password": "correct-password",
            },
        )
        assert login.status_code == 200, login.text
        token = login.json()["access_token"]

        headers = {"Authorization": f"Bearer {token}"}
        assert client.get("/knowledge/documents").status_code == 401

        profile = client.post("/profiles/farm", json={
            "farm_name": "MySQL Farm", "district": "Mbale", "crops": "maize", "farm_size": 2.0,
        }, headers=headers)
        assert profile.status_code == 201, profile.text
        profile_id = profile.json()["id"]
        assert client.put(f"/profiles/farm/{profile_id}", json={"farm_size": 3.0}, headers=headers).status_code == 200
        assert client.get("/profiles/farm", headers=headers).json()[0]["farm_size"] == 3.0

        app.dependency_overrides[get_recommendation_service] = lambda: FakeRecommendation()
        recommendation = client.get("/recommendations/initial", headers=headers)
        assert recommendation.status_code == 200, recommendation.text

        entry = client.post("/logbook/", json={
            "activity_type": "PLANTING", "date": "2026-08-23", "crop": "maize", "field": "north", "note": "start",
        }, headers=headers)
        assert entry.status_code == 200, entry.text
        entry_id = entry.json()["id"]
        assert client.put(f"/logbook/{entry_id}", json={"note": "done"}, headers=headers).status_code == 200
        assert len(client.get("/logbook/", headers=headers).json()) == 1

        embeddings = ControlledEmbeddings()
        with SessionLocal() as db:
            ingested = ingest_document(
                db, title="Controlled maize notes", source_identifier="fixture:mysql-maize",
                text="Plant maize after reliable rains.", source_type="fixture", embedding_service=embeddings,
            )
            assert ingested.created

        retriever = KnowledgeRetriever(embeddings, top_k=3, threshold=0.25)
        with patch("app.chat.OpenAI", FakeOpenAI), patch("app.chat.validate_chat_content", return_value=None), patch("app.chat.KnowledgeRetriever", return_value=retriever):
            chat = client.post("/chats", json={"content": "When should I plant maize?"}, headers=headers)
            assert chat.status_code == 200, chat.text
            events = [json.loads(line[6:]) for line in chat.text.splitlines() if line.startswith("data: ")]
            assert events[0]["content"] == FakeResponse.output_text
            assert events[1]["citations"][0]["source"] == "fixture:mysql-maize"
            conversations = client.get("/conversations", headers=headers).json()
            assert len(conversations) == 1
            messages = client.get(f"/conversations/{conversations[0]['id']}/messages", headers=headers).json()
            assert [message["role"] for message in messages] == ["user", "assistant"]

            app.dependency_overrides[get_speech_to_text] = lambda: FakeSTT()
            app.dependency_overrides[get_text_to_speech] = lambda: FakeTTS()
            voice = client.post(
                "/voice/chat", files={"audio": ("clip.wav", b"controlled-audio", "audio/wav")}, headers=headers
            )
            assert voice.status_code == 200, voice.text
            assert voice.json()["audio_base64"]

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "beans.txt"
            source.write_text("Bean rows need careful spacing.", encoding="utf-8")
            with SessionLocal() as db:
                first = run_ingestion_sweep(db, directory=Path(directory), embedding_service=embeddings)
                second = run_ingestion_sweep(db, directory=Path(directory), embedding_service=embeddings)
                assert first.documents_created == 1
                assert second.documents_skipped == 1

        with SessionLocal() as db:
            assert db.query(ConversationMessage).count() == 4
            assert db.query(Citation).count() >= 2
            assert db.query(IngestionRun).count() == 2
    finally:
        app.dependency_overrides.clear()
        with SessionLocal() as db:
            db.query(Citation).delete()
            db.query(ConversationMessage).delete()
            db.query(Conversation).delete()
            db.query(LogbookEntry).delete()
            db.query(FarmProfile).delete()
            db.query(Chunk).delete()
            db.query(Document).delete()
            db.query(IngestionRun).delete()
            db.query(User).filter(User.username == "mysql-alice").delete()
            db.commit()
        client.close()
        engine.dispose()


@unittest.skipUnless(
    MYSQL_TEST_DATABASE_URL,
    "MYSQL_TEST_DATABASE_URL is required for the Docker MySQL integration test",
)
class MySQLAuthenticationIntegrationTests(unittest.TestCase):
    def test_signup_login_token_and_protected_route(self):
        completed = subprocess.run(
            [sys.executable, __file__, "--mysql-child"],
            env=os.environ.copy(),
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            completed.returncode,
            0,
            completed.stdout + completed.stderr,
        )


if __name__ == "__main__" and "--mysql-child" in sys.argv:
    run_mysql_flow()
elif __name__ == "__main__":
    unittest.main()
