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
the Guardrails token in this repository. Until both validators are installed,
importing `main` will fail at its `from guardrails.hub import ...` imports.

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
