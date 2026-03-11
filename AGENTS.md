# Repository Guidelines

## Project Structure & Module Organization

Source code lives under `src/` and is split by responsibility:

- `src/openai_oauth_cli/`: login CLI, SQLite account store, OAuth callback handling, and page-state login flow
- `src/openai_register/`: registration and verify-login CLI, diagnostics, and registration state machine
- `src/openai_auth_core/`: shared browser, mailbox, callback, and OAuth helpers extracted from both flows

Tests live under `tests/`. Keep unit tests near the module area they cover, and use `tests/e2e/` only for gated live browser flows. Design notes and implementation plans live in `docs/plans/`.

## Build, Test, and Development Commands

- `uv sync --group dev`: install project and development tools
- `uv run pytest`: run the full test suite
- `uv run ruff check .`: run lint checks
- `uv run ty check`: run static type checks
- `uv build`: build the package with `uv_build`
- `uv run openai-oauth-cli ...`: run the login CLI locally
- `uv run openai-register ...`: run the registration CLI locally

Live E2E is opt-in:

```bash
OPENAI_LIVE_E2E=1 OPENAI_E2E_DB_PATH=/abs/path/accounts.sqlite3 \
uv run pytest tests/e2e/test_live_flows.py -m live_e2e -v
```

## Coding Style & Naming Conventions

Target Python 3.12. Use 4-space indentation, explicit type hints, and `from __future__ import annotations` in module files. Follow existing naming patterns: `snake_case` for functions and modules, `PascalCase` for classes and dataclasses, and descriptive protocol names such as `RegistrationBrowser` or `OAuthLoginBrowser`.

Use `ruff` for linting and `ty` for typing. Keep CLI output contracts stable: success goes to stdout, progress and failures go to stderr.

## Testing Guidelines

Use `pytest` for all tests. Name files `test_*.py` and keep test names behavior-focused, for example `test_login_command_prints_refresh_token`. Add or update regression tests for any changed behavior. There is no stated coverage gate; rely on targeted tests plus the full suite before merging.

## Commit & Pull Request Guidelines

Recent history uses Conventional Commit prefixes such as `fix:`, `docs:`, `refactor:`, and `chore:`. Keep subjects short and imperative.

PRs should include a short problem statement, the approach taken, and exact verification commands run. If you touch live-flow behavior, include any new env vars, database assumptions, and artifact or log path changes.

## Security & Configuration Tips

Do not commit SQLite databases, mailbox exports, tokens, proxies, or log artifacts. Treat `OPENAI_E2E_DB_PATH`, local `data/`, `secrets/`, and `logs/` contents as sensitive runtime material.
