# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development commands

- Python/runtime: Python 3.12, packaged entry points are `openai-oauth-cli` and `openai-register`
- Install dev dependencies: `uv sync --group dev`
- Run the default test suite: `uv run pytest -m "not live_e2e"`
- Run all tests: `uv run pytest`
- Run a single test: `uv run pytest tests/test_cli.py::test_login_command_prints_refresh_token -q`
- Lint: `uv run ruff check .`
- Type check: `uv run ty check`
- Build: `uv build`

Common targeted test runs:

- Login + DB contracts: `uv run pytest tests/test_cli.py tests/test_cli_db.py tests/test_accounts_db.py -q`
- Registration flow: `uv run pytest tests/test_register_cli.py tests/test_register_accounts_db.py tests/test_register_state_machine.py -q`
- Shared auth core: `uv run pytest tests/test_auth_core_flow.py tests/test_auth_core_oauth.py tests/test_auth_core_callback.py tests/test_auth_core_oauth_pages.py tests/test_auth_core_mailbox.py -q`

Local CLI workflows:

- Init account DB: `uv run openai-oauth-cli db init --db-path data/accounts.sqlite3`
- Import txt exports into SQLite: `uv run openai-oauth-cli db import-txt --db-path data/accounts.sqlite3 --txt-path secrets/accounts.txt`
- Inspect DB summary: `uv run openai-oauth-cli db summary --db-path data/accounts.sqlite3`
- Run login flow: `uv run openai-oauth-cli login --email you@example.com --db-path data/accounts.sqlite3`
- Run registration flow: `uv run openai-register register --email you@example.com --db-path data/accounts.sqlite3`
- Verify an existing account: `uv run openai-register verify-login --email you@example.com --db-path data/accounts.sqlite3`

Live E2E is gated behind env vars:

```bash
OPENAI_LIVE_E2E=1 \
OPENAI_E2E_DB_PATH=/absolute/path/to/accounts.sqlite3 \
uv run pytest tests/e2e/test_live_flows.py -m live_e2e -v
```

## Architecture

The repo has three layers:

- `src/openai_auth_core/`: shared browser, mailbox, callback, OAuth, page-classification, and timeout helpers used by both CLIs.
- `src/openai_oauth_cli/`: login CLI and the canonical SQLite account-import workflow. `cli.py` exposes `login`, `db init`, `db import-txt`, and `db summary`; `accounts_db.py` owns the SQLite schema and txt-to-SQLite sync.
- `src/openai_register/`: registration and verification CLI. It reuses the shared auth core, adds registration-specific browser/page/state-machine logic, and writes diagnostics/artifacts for failures.

Runtime flow is: load account/mailbox data from SQLite, start a localhost callback server, prime the mailbox to ignore stale verification emails, drive a headed Patchright session with a state machine, then either exchange the OAuth code for a refresh token or mark registration/verification state in SQLite.

## Contracts and invariants

- SQLite is the runtime source of truth. Txt exports are import input only.
- `openai-oauth-cli login` ignores `--accounts-file`; runtime lookup comes from `--db-path`.
- `db import-txt` updates mailbox metadata (`email`, `mail_client_id`, `mail_refresh_token`, `group_name`) but preserves SQLite-owned state such as `is_registered`, `is_primary`, and registration timestamps/errors.
- `openai-register` expects an existing `accounts` table and adds registration tracking columns if they are missing.
- Both CLIs are headed only. Do not add or rely on a `--headless` flag.
- Login success writes only the `refresh_token` to stdout.
- Registration success writes `registered:<email>`; verification success writes `verified:<email>`.
- Failures write to stderr, return a non-zero exit code, and registration failures keep a log/artifact directory under `logs/openai-register/` unless `--artifacts-dir` overrides it.
- `db summary` writes one compact JSON object.
- `BrokenPipeError` on stdout is intentionally allowed to propagate.
- Live E2E copies the source SQLite DB into a temp directory before running; it does not mutate the source DB.

## Where to look before changing behavior

- CLI/output contracts: `tests/test_cli.py`, `tests/test_cli_db.py`, `tests/test_register_cli.py`
- SQLite import/state semantics: `tests/test_accounts_db.py`, `tests/test_register_accounts_db.py`
- Login/registration state machines: `tests/test_state_machine.py`, `tests/test_register_state_machine.py`
- Shared auth-core contracts: `tests/test_auth_core_flow.py`, `tests/test_auth_core_oauth.py`, `tests/test_auth_core_callback.py`, `tests/test_auth_core_oauth_pages.py`, `tests/test_auth_core_mailbox.py`
- Live E2E gating and copied-DB behavior: `tests/e2e/conftest.py`, `tests/e2e/test_live_flows.py`

## Sensitive local data

Treat `data/`, `secrets/`, `logs/`, SQLite DBs, mailbox exports, tokens, and proxy values as sensitive local runtime material. Do not commit them.

## Private/Public Workflow

This repository is the private development source of truth. The public GitHub repository is a sanitized mirror and should be updated through a separate release flow, not by directly pushing the private branch history.

Recommended route:

1. Develop and debug in this private repository.
2. Run local verification here first:
   - `uv run pytest`
   - `uv run ruff check .`
   - `uv run ty check`
3. Merge the finished private work back into the root repository's `master`.
4. Stage the public update in `.worktrees/public-release-sanitized/`.
5. Sync the private root tree into that staging tree. If you use `rsync`, always exclude the worktree `.git` file and private/runtime material:
   ```bash
   rsync -a --delete \
     --exclude '.git' \
     --exclude '.worktrees/' \
     --exclude '.claude/' \
     --exclude '.venv/' \
     --exclude '.pytest_cache/' \
     --exclude '__pycache__/' \
     --exclude 'data/' \
     --exclude 'secrets/' \
     --exclude 'logs/' \
     --exclude '*.sqlite3' \
     <private-repo-root>/ \
     <private-repo-root>/.worktrees/public-release-sanitized/
   ```
6. In that staging tree, remove or replace anything that should not become public:
   - passwords and secrets
   - private email addresses
   - realistic mailbox/account samples
   - local-only file names and paths
7. Verify again in the sanitized tree:
   - `uv run pytest`
   - `uv run ruff check .`
   - `uv run ty check`
8. Publish the public repo from a clean sanitized tree using a public-safe author identity such as the GitHub no-reply email:
   ```bash
   cd <private-repo-root>/.worktrees/public-release-sanitized
   git add -A
   git -c user.name='Rupert-WLLP-Bai' \
       -c user.email='Rupert-WLLP-Bai@users.noreply.github.com' \
       commit -m 'chore: update sanitized public release'
   git push public public-master:master
   ```
9. After push, independently verify the remote `master` branch, latest commit author, and obvious sensitive-string scans.

Hard rules:

- Do not push the private root repository's `master` directly to the public GitHub repo.
- Do not treat the public staging worktree as the primary place for experimental development.
- Keep local runtime secrets in ignored files only.
- Keep `.worktrees/public-release-sanitized/` as the only long-lived public release worktree.
- Remove short-lived feature or parallel worktrees after their changes are merged. If a worktree is dirty, inspect it before removing it.
