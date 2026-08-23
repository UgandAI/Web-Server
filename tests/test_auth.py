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
        from app.models import Chunk, Citation, Conversation, ConversationMessage, Document, IngestionRun, User

        cls.SessionLocal = SessionLocal
        cls.User = User
        cls.Conversation = Conversation
        cls.ConversationMessage = ConversationMessage
        cls.Chunk = Chunk
        cls.Citation = Citation
        cls.Document = Document
        cls.IngestionRun = IngestionRun
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
            db.query(self.Citation).delete()
            db.query(self.ConversationMessage).delete()
            db.query(self.Conversation).delete()
            db.query(self.Chunk).delete()
            db.query(self.Document).delete()
            db.query(self.IngestionRun).delete()
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

        with self.SessionLocal() as db:
            self.assertEqual(db.query(self.Citation).count(), 1)
            persisted = db.query(self.Citation).one()
            self.assertEqual(persisted.chunk_id, expected_chunk_id)
            self.assertAlmostEqual(persisted.score, 0.9)
            assistant_message = (
                db.query(self.ConversationMessage)
                .filter(self.ConversationMessage.role == "assistant")
                .one()
            )
            self.assertEqual(persisted.message_id, assistant_message.id)

        chunks_response = self.client.get(
            f"/knowledge/documents/{expected_document_id}/chunks",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(chunks_response.status_code, 200, chunks_response.text)
        self.assertEqual([c["id"] for c in chunks_response.json()], [expected_chunk_id])

        citations_response = self.client.get(
            f"/knowledge/messages/{assistant_message.id}/citations",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(citations_response.status_code, 200, citations_response.text)
        self.assertEqual(citations_response.json(), [{
            "chunk_id": expected_chunk_id, "document_id": expected_document_id,
            "title": "Public maize notes", "source": "fixture:maize", "url": None,
            "chunk_index": 0, "score": 0.9,
        }])

    def test_knowledge_endpoints_require_authentication(self):
        self.assertEqual(self.client.get("/knowledge/documents").status_code, 401)
        self.assertEqual(self.client.get("/knowledge/documents/1/chunks").status_code, 401)
        self.assertEqual(self.client.get("/knowledge/messages/1/citations").status_code, 401)
        self.assertEqual(self.client.get("/knowledge/ingestion-runs").status_code, 401)

    def test_chunks_endpoint_404_for_unknown_document(self):
        token = self.login().json()["access_token"] if self.register().status_code == 200 else None
        response = self.client.get(
            "/knowledge/documents/999999/chunks", headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(response.status_code, 404)

    def test_citations_endpoint_hides_other_users_messages(self):
        self.assertEqual(self.register().status_code, 200)
        token = self.login().json()["access_token"]
        with self.SessionLocal() as db:
            conversation = self.Conversation(user_id=99999)
            db.add(conversation)
            db.flush()
            message = self.ConversationMessage(conversation_id=conversation.id, role="assistant", content="hi")
            db.add(message)
            db.commit()
            other_message_id = message.id
        response = self.client.get(
            f"/knowledge/messages/{other_message_id}/citations",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 404)

    def test_ingestion_runs_endpoint_lists_runs(self):
        self.assertEqual(self.register().status_code, 200)
        token = self.login().json()["access_token"]
        with self.SessionLocal() as db:
            db.add(self.IngestionRun(
                source_directory="./knowledge_sources", status="success", files_scanned=2,
                documents_created=1, documents_skipped=1, chunks_created=3,
            ))
            db.commit()
        response = self.client.get("/knowledge/ingestion-runs", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["status"], "success")

    def test_chat_requires_authentication(self):
        response = self.client.post("/chats", json={"content": "plant maize"})
        self.assertEqual(response.status_code, 401)

    @patch("app.chat.validate_chat_content", return_value=None)
    @patch("app.chat.OpenAI", _FakeOpenAI)
    @patch("app.chat.KnowledgeRetriever")
    def test_voice_chat_transcribes_and_synthesizes(self, retriever_class, _validate):
        from app.main import app
        from app.voice.router import get_speech_to_text, get_text_to_speech

        retriever_class.return_value.retrieve.return_value = []
        self.assertEqual(self.register().status_code, 200)
        token = self.login().json()["access_token"]

        class _FakeSTT:
            def transcribe(self, audio_bytes, filename="audio.wav"):
                self.received = (audio_bytes, filename)
                return "When should I plant maize?"

        class _FakeTTS:
            def synthesize(self, text):
                self.received_text = text
                return b"fake-mp3-bytes"

        fake_stt, fake_tts = _FakeSTT(), _FakeTTS()
        app.dependency_overrides[get_speech_to_text] = lambda: fake_stt
        app.dependency_overrides[get_text_to_speech] = lambda: fake_tts
        try:
            response = self.client.post(
                "/voice/chat",
                files={"audio": ("clip.wav", b"fake-audio-bytes", "audio/wav")},
                headers={"Authorization": f"Bearer {token}"},
            )
        finally:
            app.dependency_overrides.pop(get_speech_to_text, None)
            app.dependency_overrides.pop(get_text_to_speech, None)

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["transcript"], "When should I plant maize?")
        self.assertEqual(body["content"], _FakeResponse.output_text)
        self.assertEqual(body["citations"], [])
        self.assertEqual(fake_tts.received_text, _FakeResponse.output_text)
        import base64
        self.assertEqual(base64.b64decode(body["audio_base64"]), b"fake-mp3-bytes")

    def test_voice_chat_requires_authentication(self):
        response = self.client.post("/voice/chat", files={"audio": ("clip.wav", b"x", "audio/wav")})
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
