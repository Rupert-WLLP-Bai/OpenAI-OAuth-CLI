from __future__ import annotations

import asyncio
from pathlib import Path
import sqlite3
from unittest.mock import AsyncMock

import pytest

from openai_oauth_cli import cli
from openai_oauth_cli.accounts_db import AccountStore
from openai_oauth_cli.callback import CallbackResult
from openai_oauth_cli.models import AccountRecord, TokenBundle


def test_login_command_prints_refresh_token(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    run_login = AsyncMock(return_value="rt_example")
    monkeypatch.setattr(cli, "run_login", run_login)

    exit_code = cli.main(["login", "--email", "user@example.com", "--password", "pw"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip() == "rt_example"
    run_login.assert_awaited_once()


def test_login_command_reads_password_from_dotenv(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    captured_args: dict[str, object] = {}

    async def fake_run_login(**kwargs: object) -> str:
        captured_args.update(kwargs)
        return "rt_example"

    (tmp_path / ".env").write_text(f"{cli.PASSWORD_ENV_VAR}=dotenv-password\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "run_login", fake_run_login)
    monkeypatch.delenv(cli.PASSWORD_ENV_VAR, raising=False)

    exit_code = cli.main(["login", "--email", "user@example.com"])

    _ = capsys.readouterr()
    assert exit_code == 0
    assert captured_args["password"] == "dotenv-password"
    assert captured_args["db_path"] == str(cli.DEFAULT_DB_PATH)


def test_login_command_forwards_mail_provider_choice(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured_args: dict[str, object] = {}

    async def fake_run_login(**kwargs: object) -> str:
        captured_args.update(kwargs)
        return "rt_example"

    monkeypatch.setattr(cli, "run_login", fake_run_login)

    exit_code = cli.main(["login", "--email", "user@example.com", "--password", "pw", "--mail-provider", "graph"])

    _ = capsys.readouterr()
    assert exit_code == 0
    assert captured_args["mail_provider"] == "graph"


def test_login_command_requires_password_when_flag_and_env_missing(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv(cli.PASSWORD_ENV_VAR, raising=False)

    exit_code = cli.main(["login", "--email", "user@example.com"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert captured.err == (
        f"account password is required. Pass --password or set {cli.PASSWORD_ENV_VAR}.\n"
    )


def test_login_command_reports_missing_or_uninitialized_db(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    db_path = tmp_path / "accounts.sqlite3"

    exit_code = cli.main(["login", "--email", "user@example.com", "--password", "pw", "--db-path", str(db_path)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert captured.err == (
        "login database is missing or uninitialized at "
        f"{db_path}. Run `openai-oauth-cli db init --db-path {db_path}` "
        "and `openai-oauth-cli db import-txt --db-path "
        f"{db_path} --txt-path <accounts.txt>`.\n"
    )


def test_login_command_reports_empty_initialized_db_with_import_guidance(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    db_path = tmp_path / "accounts.sqlite3"
    AccountStore(db_path).init_db()

    exit_code = cli.main(["login", "--email", "user@example.com", "--password", "pw", "--db-path", str(db_path)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert captured.err == (
        "login database has no imported accounts at "
        f"{db_path}. Run `openai-oauth-cli db import-txt --db-path {db_path} "
        "--txt-path <accounts.txt>`.\n"
    )


def test_run_login_preserves_missing_email_error_when_db_is_populated(tmp_path: Path) -> None:
    db_path = tmp_path / "accounts.sqlite3"
    AccountStore(db_path).init_db()

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO accounts (
                email,
                mail_client_id,
                mail_refresh_token,
                group_name,
                is_registered,
                is_primary,
                notes,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "present@example.com",
                "mail-client-id",
                "mail-refresh-token",
                "group-a",
                1,
                0,
                "",
                "2026-03-10T00:00:00+00:00",
                "2026-03-10T00:00:00+00:00",
            ),
        )

    with pytest.raises(ValueError, match="account not found for email: missing@example.com"):
        asyncio.run(
            cli.run_login(
                email="missing@example.com",
                password="pw",
                accounts_file=str(tmp_path / "missing-accounts.txt"),
                db_path=str(db_path),
                callback_port=1455,
                timeout=30,
                proxy=None,
            )
        )


def test_run_login_loads_account_from_sqlite_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "accounts.sqlite3"
    store = AccountStore(db_path)
    store.init_db()

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO accounts (
                email,
                mail_client_id,
                mail_refresh_token,
                group_name,
                is_registered,
                is_primary,
                notes,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "user@example.com",
                "mail-client-id",
                "mail-refresh-token",
                "group-a",
                1,
                0,
                "",
                "2026-03-10T00:00:00+00:00",
                "2026-03-10T00:00:00+00:00",
            ),
        )

    monkeypatch.setattr(cli, "DEFAULT_DB_PATH", db_path, raising=False)

    captured: dict[str, object] = {}

    class FakeCallbackServer:
        def __init__(self, *, port: int) -> None:
            captured["callback_port"] = port

        async def start(self) -> None:
            captured["server_started"] = True

        async def wait_for_result(self, *, timeout: float) -> CallbackResult:
            captured["callback_timeout"] = timeout
            return CallbackResult(code="oauth-code", state="state-123")

        async def stop(self) -> None:
            captured["server_stopped"] = True

    class FakeBrowser:
        def __init__(
            self,
            *,
            proxy: str | None,
            callback_port: int,
            callback_task: asyncio.Task[CallbackResult],
        ) -> None:
            captured["proxy"] = proxy
            captured["browser_callback_port"] = callback_port
            captured["callback_task"] = callback_task

        async def __aenter__(self) -> FakeBrowser:
            return self

        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
            captured["browser_closed"] = True

        async def open_authorization_page(self, auth_url: str) -> None:
            captured["auth_url"] = auth_url

    class FakeLoginStateMachine:
        def __init__(self, *, browser: FakeBrowser, code_provider: object) -> None:
            captured["browser"] = browser
            captured["code_provider"] = code_provider

        async def complete_login(
            self,
            *,
            account: AccountRecord,
            email: str,
            password: str,
            timeout: int,
        ) -> str:
            captured["account"] = account
            captured["email"] = email
            captured["password"] = password
            captured["timeout"] = timeout
            return "callback"

    class FakeProvider:
        def __init__(self, *, proxy: str | None) -> None:
            captured["provider_proxy"] = proxy

        async def prime_inbox(self, *, account: AccountRecord) -> None:
            captured["primed_account"] = account.email

    async def fake_exchange_code_for_tokens(
        *,
        code: str,
        code_verifier: str,
        redirect_uri: str,
        proxy: str | None = None,
    ) -> TokenBundle:
        captured["exchange_code"] = code
        captured["code_verifier"] = code_verifier
        captured["redirect_uri"] = redirect_uri
        captured["exchange_proxy"] = proxy
        return TokenBundle(refresh_token="rt_example")

    monkeypatch.setattr(cli, "CallbackServer", FakeCallbackServer)
    monkeypatch.setattr(cli, "PatchrightBrowser", FakeBrowser)
    monkeypatch.setattr(cli, "LoginStateMachine", FakeLoginStateMachine)
    def fake_create_mail_provider(
        account: object,
        *,
        provider_choice: str = "auto",
        proxy: str | None = None,
    ) -> FakeProvider:
        captured["provider_choice"] = provider_choice
        return FakeProvider(proxy=proxy)

    monkeypatch.setattr(cli, "create_mail_provider", fake_create_mail_provider)
    monkeypatch.setattr(cli, "exchange_code_for_tokens", fake_exchange_code_for_tokens)
    monkeypatch.setattr(cli, "make_pkce_material", lambda: ("code-verifier-123", "challenge-123", "state-123"))

    refresh_token = asyncio.run(
        cli.run_login(
            email="user@example.com",
            password="pw",
            accounts_file=str(tmp_path / "missing-accounts.txt"),
            callback_port=1455,
            timeout=30,
            proxy=None,
        )
    )

    account = captured["account"]

    assert refresh_token == "rt_example"
    assert isinstance(account, AccountRecord)
    assert account.email == "user@example.com"
    assert account.mail_client_id == "mail-client-id"
    assert account.mail_refresh_token == "mail-refresh-token"
    assert captured["email"] == "user@example.com"
    assert captured["password"] == "pw"
    assert captured["timeout"] == 30
    assert captured["provider_choice"] == "auto"
    assert captured["primed_account"] == "user@example.com"


def test_login_parser_rejects_headless_flag() -> None:
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["login", "--email", "user@example.com", "--headless"])
