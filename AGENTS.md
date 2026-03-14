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

## Private/Public Workflow

This repository now has two roles:

- the current root repository is the private source of truth for day-to-day development
- the public GitHub repository is a sanitized mirror and must not receive the private local history directly

Recommended workflow:

- Do normal feature work in this private repository first.
- Verify local changes here with `uv run pytest`, `uv run ruff check .`, and `uv run ty check`.
- Merge the finished private work back to the root repository's `master` before preparing the public mirror.
- Treat `.worktrees/public-release-sanitized/` as public-release staging only, not as the main development branch.
- Before updating the public GitHub repo, copy the intended tree into the sanitized staging area, remove or replace secrets, private emails, realistic account samples, and local-only paths, then verify again there.
- Publish the public repo from a clean sanitized tree with a public-safe git identity such as the GitHub no-reply address.
- Never push this private repository's `master` or feature branches directly to the public GitHub repository.

Recommended public mirror commands:

```bash
# 1. Sync the private root tree into the sanitized public worktree.
# IMPORTANT: exclude the worktree .git file and private/runtime material.
rsync -a --delete \
  --exclude '.git' \
  --exclude '.worktrees/' \
  --exclude '.claude/' \
  --exclude '.venv/' \
  --exclude '.pytest_cache/' \
  --exclude '__pycache__/' \
  --exclude 'docs/plans/' \
  --exclude 'data/' \
  --exclude 'secrets/' \
  --exclude 'logs/' \
  --exclude '*.sqlite3' \
  /path/to/private/repo/ \
  /path/to/private/repo/.worktrees/public-release-sanitized/

# 2. Verify, commit with the public-safe identity, then push the sanitized branch.
cd /path/to/private/repo/.worktrees/public-release-sanitized
uv sync --group dev
uv run pytest
uv run ruff check .
uv run ty check
git add -A
git -c user.name='Rupert-WLLP-Bai' \
    -c user.email='Rupert-WLLP-Bai@users.noreply.github.com' \
    commit -m 'chore: update sanitized public release'
git push public public-master:master
```

Release checklist for the public mirror:

- confirm `.env`, `data/`, `secrets/`, `logs/`, SQLite files, tokens, and proxies are excluded
- confirm `docs/plans/` is excluded from the public mirror sync
- confirm public docs and examples do not contain private credentials or realistic account samples
- run verification in the sanitized tree
- re-check the published remote `master` after push
- confirm `git status --short --branch` in `.worktrees/public-release-sanitized/` is clean after push

Temporary worktree cleanup:

- remove short-lived development worktrees after their changes are merged
- keep `.worktrees/public-release-sanitized/` in place as the long-lived public release staging tree
- if a temporary worktree still has uncommitted changes, inspect it before removal instead of deleting it blindly
