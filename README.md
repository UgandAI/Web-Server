Environment variables
---------------------

```shell
VERIFIED_USERS=Bob,John,Aran,Yirga,Brad
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
without the optional Hub validators so authentication and health endpoints can
run locally; chat validation is enabled when both validators are installed.

The modular health application (`app.main:app`) does not import the Hub
validators and can be used after installing `requirements.txt`.

Alembic migrations
------------------

Alembic reads `DATABASE_URL` from the centralized application settings and uses
the local SQLite default when the variable is not set:

```shell
alembic current
alembic heads
```

Local MySQL with Docker Compose
-------------------------------

Start MySQL and the modular FastAPI health service:

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
