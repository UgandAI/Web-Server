Environment variables
---------------------

```shell
DATABASE_URL=sqlite:///./database.db
JWT_SECRET=replace-with-at-least-32-random-bytes
VERIFIED_USERS=farmer@example.com
OPENAI_API_KEY=replace-with-your-api-key
OPENAI_MODEL=replace-with-an-available-responses-api-model
```

Local installation
------------------

Create and activate a virtual environment, then install the declared Python
dependencies:

```shell
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Guardrails validators
---------------------

`NSFWText` and `RestrictToTopic` are distributed through Guardrails Hub rather
than as dependencies that `pip install -r requirements.txt` can install. Install
both validators into the active virtual environment:

```shell
guardrails hub install hub://guardrails/nsfw_text
guardrails hub install hub://tryolabs/restricttotopic
```

Guardrails Hub currently requires the Guardrails CLI to be configured with an
authenticated Hub account before it will install these validators. Do not store
the Guardrails token in this repository. The application remains importable
without usable optional Hub validators. Chat validation is enabled when both
validators are installed; the API remains runnable when they are unavailable.

Alembic migrations
------------------

Alembic reads `DATABASE_URL` from the centralized application settings and uses
the local SQLite default when the variable is not set:

```shell
alembic current
alembic heads
```

Start the canonical API:

```shell
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Local MySQL with Docker Compose
-------------------------------

Start MySQL and the canonical FastAPI service:

```shell
docker compose up --build -d
docker compose exec backend alembic upgrade head
```

Run the MySQL authentication integration test from a local virtual environment:

```shell
MYSQL_TEST_DATABASE_URL=mysql+pymysql://ugandai:localdev@127.0.0.1:3307/ugandai \
python -m unittest -v tests.test_auth_mysql
```

The existing SQLite authentication tests remain available with:

```shell
python -m unittest -v tests.test_auth
```
