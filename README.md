# OpenAI OAuth CLI

Chinese README: [README.zh-CN.md](README.zh-CN.md)

Python CLIs for:

- automating the OpenAI web login flow and printing the resulting `refresh_token`
- automating ChatGPT account registration and updating local SQLite account state

## What It Does

- accepts an OpenAI account email address
- reads the account password from `--password` or `OPENAI_ACCOUNT_PASSWORD`
- launches a `patchright` browser session
- drives the login flow through a page-state machine
- looks up mailbox metadata from a local SQLite database
- captures the OAuth callback on localhost
- exchanges the authorization code for tokens
- prints only the `refresh_token`

## SQLite Account Workflow

Initialize the database, sync mailbox metadata from one or more txt exports, and inspect the summary before running `login`:

```bash
uv run openai-oauth-cli db init --db-path data/accounts.sqlite3
uv run openai-oauth-cli db import-txt \
  --db-path data/accounts.sqlite3 \
  --txt-path secrets/example_accounts.txt
uv run openai-oauth-cli db summary --db-path data/accounts.sqlite3
```

`db summary` prints one compact JSON object with the total account count and per-group counts, for example:

```json
{"accounts":42,"groups":{"group-a":21,"group-b":21}}
```

`db import-txt` syncs mailbox metadata into SQLite. It updates:

- `email`
- `mail_client_id`
- `mail_refresh_token`
- `group_name`

`db import-txt` does not derive or overwrite SQLite-owned state such as:

- `is_registered`
- `is_primary`
- registration timestamps and errors

Repeat `--txt-path` to sync multiple files in order:

```bash
uv run openai-oauth-cli db import-txt \
  --db-path data/accounts.sqlite3 \
  --txt-path secrets/example_accounts.txt \
  --txt-path secrets/example_accounts_extra.txt
```

If you want to inspect those flags directly, query the SQLite database:

```bash
sqlite3 data/accounts.sqlite3 \
  "SELECT email, is_registered, is_primary FROM accounts ORDER BY lower(email);"
```

## Password Configuration

The CLIs read the password from `--password` or `OPENAI_ACCOUNT_PASSWORD`.

For local development, keep the real value in `.env` and keep `.env.example` checked in without secrets:

```dotenv
# .env
OPENAI_ACCOUNT_PASSWORD=your-password
```

```dotenv
# .env.example
OPENAI_ACCOUNT_PASSWORD=
```

The CLIs load `.env` from the current working directory with `python-dotenv`, so keeping the real value in a local `.env` file is enough for normal development.

## Local Account Admin

Run the localhost account admin server with:

```bash
uv run openai-oauth-cli db serve --db-path data/accounts.sqlite3
```

Optional flags:

- `--port`
- `--proxy`
- `--no-open-browser`

The admin server:

- binds only to `127.0.0.1`
- prints a localhost URL
- opens that URL in your browser unless `--no-open-browser` is set
- keeps SQLite as the source of truth for current group and status state
- fetches inbox contents live from wyx66 and does not persist inbox messages locally

The admin APIs and UI do not expose `mail_refresh_token` by default.

## Login

After the database is initialized and populated, run:

```bash
uv run openai-oauth-cli login --email you@example.com --db-path data/accounts.sqlite3
```

`login` reads account metadata and state from `--db-path`. It does not use the txt exports at runtime. If the database is missing or uninitialized, run `db init` and `db import-txt` first.

Optional login flags:

- `--password`
- `--db-path`
- `--callback-port`
- `--timeout`
- `--proxy`
- `--accounts-file` deprecated and ignored by `login`

## Registration CLI

`openai-register` is a standalone registration flow. It does not replace the login package; it complements it.

Registration:

```bash
uv run openai-register register --email you@example.com --db-path data/accounts.sqlite3
```

Verification-only:

```bash
uv run openai-register verify-login --email you@example.com --db-path data/accounts.sqlite3
```

Registration and verification flags:

- `--db-path`
- `--password`
- `--timeout`
- `--callback-port`
- `--proxy`
- `--artifacts-dir`

Both CLIs force a headed browser session. There is no `--headless` mode.

## Defaults

- password source: `--password` or `OPENAI_ACCOUNT_PASSWORD`
- default database path: `data/accounts.sqlite3`
- `db import-txt` requires at least one explicit `--txt-path`

## Registration Database Requirements

`openai-register` expects an existing SQLite `accounts` table with:

- `email`
- `mail_client_id`
- `mail_refresh_token`
- `is_registered`

The command will add these tracking columns if they are missing:

- `registered_at`
- `last_registration_attempt_at`
- `last_registration_error`

## Output Contract

Login success:

- stdout contains only the `refresh_token`
- stderr contains progress and errors

Login failure:

- stdout is empty
- stderr contains the failure message
- exit code is non-zero

Registration success:

- stdout contains `registered:<email>`

Verification success:

- stdout contains `verified:<email>`

Registration or verification failure:

- stdout is empty
- stderr contains the failure message
- a log directory is created under `logs/openai-register/`

## Live E2E Tests

The live end-to-end suite is under `tests/e2e/`.

- default behavior: skipped
- enable by setting `OPENAI_LIVE_E2E=1`
- required database input: `OPENAI_E2E_DB_PATH=/absolute/path/to/accounts.sqlite3`

Recommended invocation:

```bash
OPENAI_LIVE_E2E=1 \
OPENAI_E2E_DB_PATH=/absolute/path/to/accounts.sqlite3 \
uv run pytest tests/e2e/test_live_flows.py -m live_e2e -v
```

The live suite copies the SQLite database into a temporary test directory before running. Registration and verification state changes happen against the copied database, not the source database.

Optional overrides:

- `OPENAI_E2E_REGISTERED_EMAIL`
- `OPENAI_E2E_UNREGISTERED_VERIFY_EMAIL`
- `OPENAI_E2E_UNREGISTERED_REGISTER_EMAIL`
- `OPENAI_E2E_TIMEOUT`
- `OPENAI_E2E_PROXY`
- `OPENAI_E2E_CALLBACK_PORT`
- `OPENAI_E2E_ARTIFACTS_DIR`

If live E2E is enabled but the database does not contain enough suitable accounts, the scenario skips with a concrete reason.
