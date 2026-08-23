import os
from pathlib import Path
import subprocess
import sys
import unittest


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
    from app.models import User

    client = TestClient(app)
    try:
        with SessionLocal() as db:
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

        protected = client.get(
            "/knowledge/documents",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert protected.status_code == 200, protected.text
        assert isinstance(protected.json(), list)
    finally:
        with SessionLocal() as db:
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
