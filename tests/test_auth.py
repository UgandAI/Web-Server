import os
from pathlib import Path
import tempfile
import unittest

import guardrails.hub
import jwt
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from passlib.hash import bcrypt
from tortoise import Tortoise


class _UnavailableHubValidator:
    def __init__(self, *args, **kwargs):
        pass


guardrails.hub.NSFWText = _UnavailableHubValidator
guardrails.hub.RestrictToTopic = _UnavailableHubValidator


class AuthenticationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_environment = {
            key: os.environ.get(key)
            for key in ("DATABASE_URL", "OPENAI_API_KEY", "VERIFIED_USERS")
        }
        cls.temp_directory = tempfile.TemporaryDirectory()
        database_path = Path(cls.temp_directory.name) / "auth.db"
        os.environ["DATABASE_URL"] = f"sqlite:///{database_path}"
        os.environ["OPENAI_API_KEY"] = "local-test-placeholder"
        os.environ["VERIFIED_USERS"] = "alice"

        repository_root = Path(__file__).resolve().parents[1]
        alembic_config = Config(repository_root / "alembic.ini")
        command.upgrade(alembic_config, "head")

        import main
        from app.db.session import SessionLocal
        from app.models import User

        cls.main = main
        cls.SessionLocal = SessionLocal
        cls.User = User
        cls.client = TestClient(main.app)

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
            db.query(self.User).delete()
            db.commit()

    def register(self, password="correct-password"):
        return self.client.post(
            "/users/register",
            json={"username": "alice", "password": password},
        )

    def login(self, password="correct-password"):
        return self.client.post(
            "/api/token",
            data={"username": "alice", "password": password},
        )

    def test_successful_registration(self):
        response = self.register()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["username"], "alice")
        self.assertIsInstance(response.json()["id"], int)

        with self.SessionLocal() as db:
            user = (
                db.query(self.User)
                .filter(self.User.username == "alice")
                .one()
            )
            self.assertNotEqual(user.hashed_password, "correct-password")
            self.assertTrue(
                bcrypt.verify("correct-password", user.hashed_password)
            )

        self.assertFalse(Tortoise._inited)

    def test_signup_and_login_aliases(self):
        signup = self.client.post(
            "/signup",
            json={
                "username": "alice",
                "email": "alice@example.test",
                "password": "correct-password",
            },
        )
        self.assertEqual(signup.status_code, 200)
        self.assertEqual(signup.json()["email"], "alice@example.test")

        login = self.client.post(
            "/login",
            data={"username": "alice", "password": "correct-password"},
        )
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.json()["token_type"], "bearer")

    def test_duplicate_username_rejection(self):
        self.assertEqual(self.register().status_code, 200)

        response = self.register()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {"detail": "Username which is already in use."},
        )

    def test_successful_login(self):
        self.assertEqual(self.register().status_code, 200)

        response = self.login()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["token_type"], "bearer")
        payload = jwt.decode(
            response.json()["access_token"],
            self.main.JWT_SECRET,
            algorithms=["HS256"],
        )
        self.assertEqual(payload["username"], "alice")
        self.assertIn("password_hash", payload)
        self.assertNotEqual(payload["password_hash"], "correct-password")
        self.assertNotIn("exp", payload)

    def test_incorrect_password_rejection(self):
        self.assertEqual(self.register().status_code, 200)

        response = self.login(password="incorrect-password")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json(),
            {"detail": "Invalid Username or Password"},
        )

    def test_protected_route_with_valid_token(self):
        self.assertEqual(self.register().status_code, 200)
        token = self.login().json()["access_token"]

        response = self.client.post(
            "/items/?str=value",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), "Hello world")

    def test_protected_route_without_token(self):
        response = self.client.post("/items/?str=value")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"detail": "Not authenticated"})


if __name__ == "__main__":
    unittest.main()
