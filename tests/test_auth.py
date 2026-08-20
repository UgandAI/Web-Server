import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from unittest.mock import MagicMock

import jwt
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient


class _FakeResponse:
    output_text = "Plant maize after the rains begin."


def _fake_respond(_self, messages):
    assert messages[-1] == {"role": "user", "content": "When should I plant maize?"}
    return _FakeResponse.output_text


class CanonicalApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_environment = {
            key: os.environ.get(key)
            for key in ("DATABASE_URL", "JWT_SECRET", "OPENAI_API_KEY", "OPENAI_MODEL", "VERIFIED_USERS")
        }
        cls.temp_directory = tempfile.TemporaryDirectory()
        database_path = Path(cls.temp_directory.name) / "api.db"
        os.environ.update({
            "DATABASE_URL": f"sqlite:///{database_path}",
            "JWT_SECRET": "test-secret-with-at-least-32-bytes",
            "OPENAI_API_KEY": "test-key",
            "OPENAI_MODEL": "test-model",
            "VERIFIED_USERS": "farmer@example.com",
        })
        repository_root = Path(__file__).resolve().parents[1]
        command.upgrade(Config(repository_root / "alembic.ini"), "head")

        from app.main import app
        from app.db.session import SessionLocal
        from app.models import Conversation, ConversationMessage, User

        cls.SessionLocal = SessionLocal
        cls.User = User
        cls.Conversation = Conversation
        cls.ConversationMessage = ConversationMessage
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        from app.db.session import engine
        cls.client.close()
        engine.dispose()
        cls.temp_directory.cleanup()
        for key, value in cls.original_environment.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def setUp(self):
        with self.SessionLocal() as db:
            db.query(self.ConversationMessage).delete()
            db.query(self.Conversation).delete()
            db.query(self.User).delete()
            db.commit()

    def register(self):
        return self.client.post("/users/register", json={
            "username": "farmer@example.com",
            "password": "correct-password",
            "location": "Mbale",
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
    @patch("app.openai_service.OpenAIResponsesService.respond", _fake_respond)
    def test_authenticated_chat_persists_conversation(self, _validate):
        self.assertEqual(self.register().status_code, 200)
        token = self.login().json()["access_token"]
        response = self.client.post(
            "/chats",
            json={"sender": "user", "content": "When should I plant maize?"},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["content"], _FakeResponse.output_text)
        self.assertEqual(response.json()["sender"], "user")
        self.assertIsNone(response.json()["thread_id"])
        with self.SessionLocal() as db:
            self.assertEqual(db.query(self.Conversation).count(), 1)
            self.assertEqual(db.query(self.ConversationMessage).count(), 2)

    @patch("app.chat.validate_chat_content", return_value=None)
    @patch("app.openai_service.OpenAIResponsesService.respond", _fake_respond)
    def test_week2_conversation_send_and_history(self, _validate):
        self.assertEqual(self.register().status_code, 200)
        token = self.login().json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        created = self.client.post("/conversations", headers=headers)
        self.assertEqual(created.status_code, 201, created.text)
        conversation_id = created.json()["id"]

        sent = self.client.post(
            f"/conversations/{conversation_id}/messages",
            json={"content": "When should I plant maize?"},
            headers=headers,
        )
        self.assertEqual(sent.status_code, 201, sent.text)
        self.assertEqual(sent.json()["user_message"]["role"], "user")
        self.assertEqual(sent.json()["assistant_message"]["content"], _FakeResponse.output_text)

        history = self.client.get(
            f"/conversations/{conversation_id}/messages", headers=headers
        )
        self.assertEqual(history.status_code, 200, history.text)
        self.assertEqual([item["role"] for item in history.json()], ["user", "assistant"])
        with self.SessionLocal() as db:
            self.assertEqual(db.query(self.ConversationMessage).count(), 2)

    def test_conversation_routes_require_authentication(self):
        self.assertEqual(self.client.post("/conversations").status_code, 401)
        self.assertEqual(self.client.get("/conversations/1/messages").status_code, 401)

    @patch("app.openai_service.OpenAI")
    def test_openai_wrapper_uses_responses_api_without_remote_storage(self, openai):
        response = MagicMock(output_text="Controlled response")
        openai.return_value.responses.create.return_value = response
        from app.openai_service import OpenAIResponsesService

        service = OpenAIResponsesService()
        messages = [{"role": "user", "content": "When should I plant maize?"}]
        self.assertEqual(service.respond(messages), "Controlled response")
        openai.return_value.responses.create.assert_called_once_with(
            model="test-model", input=messages, store=False
        )

    def test_chat_requires_authentication(self):
        response = self.client.post("/chats", json={"content": "plant maize"})
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
