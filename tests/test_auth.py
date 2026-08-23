import os
from pathlib import Path
import tempfile
import unittest
import json
from unittest.mock import patch

import jwt
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

# Configure the application before unittest discovery imports other test modules.
_DISCOVERY_TEMP_DIRECTORY = tempfile.TemporaryDirectory()
os.environ.update({
    "DATABASE_URL": f"sqlite:///{Path(_DISCOVERY_TEMP_DIRECTORY.name) / 'api.db'}",
    "JWT_SECRET": "test-secret-with-at-least-32-bytes",
    "OPENAI_API_KEY": "test-key",
    "OPENAI_MODEL": "test-model",
    "VERIFIED_USERS": "farmer@example.com",
})


class _FakeResponse:
    output_text = "Plant maize after the rains begin."


class _FakeResponses:
    def create(self, **kwargs):
        self.request = kwargs
        return _FakeResponse()


class _FakeOpenAI:
    responses = _FakeResponses()

    def __init__(self, **kwargs):
        pass


class CanonicalApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_environment = {
            key: os.environ.get(key)
            for key in ("DATABASE_URL", "JWT_SECRET", "OPENAI_API_KEY", "OPENAI_MODEL", "VERIFIED_USERS")
        }
        cls.temp_directory = _DISCOVERY_TEMP_DIRECTORY
        repository_root = Path(__file__).resolve().parents[1]
        command.upgrade(Config(repository_root / "alembic.ini"), "head")

        from app.main import app
        from app.db.session import SessionLocal
        from app.models import Chunk, Conversation, ConversationMessage, Document, User

        cls.SessionLocal = SessionLocal
        cls.User = User
        cls.Conversation = Conversation
        cls.ConversationMessage = ConversationMessage
        cls.Chunk = Chunk
        cls.Document = Document
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        from app.db.session import engine
        cls.client.close()
        engine.dispose()
        for key, value in cls.original_environment.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def setUp(self):
        with self.SessionLocal() as db:
            db.query(self.ConversationMessage).delete()
            db.query(self.Conversation).delete()
            db.query(self.Chunk).delete()
            db.query(self.Document).delete()
            db.query(self.User).delete()
            db.commit()

    def register(self):
        return self.client.post("/users/register", json={
            "username": "farmer@example.com",
            "password": "correct-password",
            "email": "farmer@example.com",
        })

    def login(self):
        return self.client.post("/api/token", data={
            "username": "farmer@example.com", "password": "correct-password"
        })

    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "connected"})

    def test_registration_and_login(self):
        registration = self.register()
        self.assertEqual(registration.status_code, 200, registration.text)
        self.assertNotIn("email", registration.json())
        login = self.login()
        self.assertEqual(login.status_code, 200, login.text)
        self.assertEqual(login.json()["token_type"], "bearer")
        self.assertTrue(login.json()["access_token"])
        claims = jwt.decode(
            login.json()["access_token"],
            "test-secret-with-at-least-32-bytes",
            algorithms=["HS256"],
        )
        self.assertEqual(claims["username"], "farmer@example.com")
        self.assertIn("password_hash", claims)

    def test_registration_requires_allowlist(self):
        response = self.client.post("/users/register", json={
            "username": "unknown@example.com", "password": "password"
        })
        self.assertEqual(response.status_code, 400)

    @patch("app.chat.validate_chat_content", return_value=None)
    @patch("app.chat.OpenAI", _FakeOpenAI)
    @patch("app.chat.KnowledgeRetriever")
    def test_authenticated_chat_persists_conversation(self, retriever_class, _validate):
        retriever_class.return_value.retrieve.return_value = []
        self.assertEqual(self.register().status_code, 200)
        token = self.login().json()["access_token"]
        response = self.client.post(
            "/chats",
            json={"sender": "user", "content": "When should I plant maize?"},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
        self.assertEqual(events, [{"content": _FakeResponse.output_text}])
        with self.SessionLocal() as db:
            self.assertEqual(db.query(self.Conversation).count(), 1)
            self.assertEqual(db.query(self.ConversationMessage).count(), 2)

    @patch("app.chat.validate_chat_content", return_value=None)
    @patch("app.chat.OpenAI", _FakeOpenAI)
    @patch("app.chat.KnowledgeRetriever")
    def test_chat_citations_match_retrieved_records(self, retriever_class, _validate):
        from app.knowledge.retrieval import RetrievedChunk
        self.assertEqual(self.register().status_code, 200)
        token = self.login().json()["access_token"]
        with self.SessionLocal() as db:
            document = self.Document(
                title="Public maize notes", source_identifier="fixture:maize", source_url=None,
                source_type="fixture", checksum="a" * 64,
            )
            db.add(document)
            db.flush()
            chunk = self.Chunk(document_id=document.id, chunk_index=0, text="Plant with established rains.", embedding="[1.0,0.0]")
            db.add(chunk)
            db.commit()
            db.refresh(chunk)
            expected_document_id, expected_chunk_id = document.id, chunk.id
        def retrieve(db, _query):
            chunk = db.query(self.Chunk).filter(self.Chunk.id == expected_chunk_id).one()
            return [RetrievedChunk(chunk, 0.9)]
        retriever_class.return_value.retrieve.side_effect = retrieve
        response = self.client.post(
            "/chats", json={"content": "When should I plant maize?"},
            headers={"Authorization": f"Bearer {token}"},
        )
        events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
        citation = events[1]["citations"][0]
        self.assertEqual(citation["document_id"], expected_document_id)
        self.assertEqual(citation["chunk_id"], expected_chunk_id)
        self.assertEqual(citation["source"], "fixture:maize")

    def test_chat_requires_authentication(self):
        response = self.client.post("/chats", json={"content": "plant maize"})
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
