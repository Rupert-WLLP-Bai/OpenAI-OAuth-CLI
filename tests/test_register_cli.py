from __future__ import annotations

from pathlib import Path
from unittest.mock import ANY, AsyncMock

import pytest

from openai_register import cli
from openai_register.models import MailAccountRecord


def test_register_command_uses_password_from_environment(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured_args: dict[str, object] = {}

    async def fake_run_register(**kwargs: object) -> str:
        captured_args.update(kwargs)
        return "user@example.com"

    monkeypatch.setenv("OPENAI_ACCOUNT_PASSWORD", "env-password")
    monkeypatch.setattr(cli, "run_register", fake_run_register)

    exit_code = cli.main(
        [
            "register",
            "--email",
            "user@example.com",
            "--db-path",
            "/tmp/accounts.sqlite3",
        ]
    )

    _ = capsys.readouterr()
    assert exit_code == 0
    assert captured_args["password"] == "env-password"


def test_register_command_requires_password_flag_or_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENAI_ACCOUNT_PASSWORD", raising=False)

    exit_code = cli.main(
        [
            "register",
            "--email",
            "user@example.com",
            "--db-path",
            "/tmp/accounts.sqlite3",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert captured.err == (
        "account password is required. "
        "Pass `--password` or set `OPENAI_ACCOUNT_PASSWORD` in `.env` or the environment.\n"
    )


def test_register_command_prints_success_message(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "run_register", AsyncMock(return_value="user@example.com"))

    exit_code = cli.main(
        [
            "register",
            "--email",
            "user@example.com",
            "--db-path",
            "/tmp/accounts.sqlite3",
            "--password",
            "pw",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip() == "registered:user@example.com"


def test_verify_login_command_prints_success_message(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "run_verify_login", AsyncMock(return_value="user@example.com"))

    exit_code = cli.main(
        [
            "verify-login",
            "--email",
            "user@example.com",
            "--db-path",
            "/tmp/accounts.sqlite3",
            "--password",
            "pw",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip() == "verified:user@example.com"


def test_register_parser_rejects_headless_flag() -> None:
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["register", "--email", "user@example.com", "--db-path", "/tmp/db.sqlite3", "--headless"])


def test_run_register_marks_started_then_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[tuple[str, object]] = []
    for env_var in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        monkeypatch.delenv(env_var, raising=False)

    class FakeStore:
        def __init__(self, db_path: Path) -> None:
            calls.append(("store_init", db_path))

        def get_mail_account(self, email: str) -> MailAccountRecord:
            calls.append(("get_mail_account", email))
            return MailAccountRecord(
                email=email,
                mail_client_id="client-id",
                mail_refresh_token="mail-refresh-token",
            )

        def mark_registration_started(self, email: str) -> None:
            calls.append(("mark_started", email))

        def mark_registration_succeeded(self, email: str) -> None:
            calls.append(("mark_succeeded", email))

        def mark_registration_failed(self, email: str, error_message: str) -> None:
            calls.append(("mark_failed", (email, error_message)))

    class FakeBrowser:
        def __init__(self, *, proxy: str | None, logger: object | None = None) -> None:
            calls.append(("browser_init", proxy))

        async def __aenter__(self) -> FakeBrowser:
            calls.append(("browser_enter", None))
            return self

        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
            calls.append(("browser_exit", None))

        async def open_chatgpt(self) -> None:
            calls.append(("open_chatgpt", None))

    class FakeMachine:
        def __init__(self, *, browser: FakeBrowser, code_provider: object) -> None:
            calls.append(("machine_init", browser))

        async def complete_registration(
            self,
            *,
            account: MailAccountRecord,
            email: str,
            password: str,
            timeout: int,
        ) -> str:
            calls.append(("complete_registration", (account.email, email, password, timeout)))
            return "success"

    class FakeProvider:
        def __init__(self, *, proxy: str | None) -> None:
            calls.append(("provider_init", proxy))

        async def prime_inbox(self, *, account: MailAccountRecord) -> None:
            calls.append(("prime_inbox", account.email))

    def fake_create_mail_provider(
        account: object,
        *,
        provider_choice: str = "auto",
        proxy: str | None = None,
    ) -> FakeProvider:
        calls.append(("create_mail_provider", provider_choice))
        return FakeProvider(proxy=proxy)

    async def fake_verify_registered_account(**kwargs: object) -> None:
        calls.append(("verify_registered_account", kwargs["email"]))

    monkeypatch.setattr(cli, "RegistrationAccountStore", FakeStore)
    monkeypatch.setattr(cli, "PatchrightBrowser", FakeBrowser)
    monkeypatch.setattr(cli, "RegistrationStateMachine", FakeMachine)
    monkeypatch.setattr(cli, "create_mail_provider", fake_create_mail_provider)
    monkeypatch.setattr(cli, "verify_registered_account", fake_verify_registered_account)

    result = cli.asyncio.run(
        cli.run_register(
            email="user@example.com",
            password="pw",
            db_path=str(tmp_path / "accounts.sqlite3"),
            timeout=30,
            proxy=None,
            callback_port=1455,
            artifacts_dir=str(tmp_path / "logs"),
        )
    )

    assert result == "user@example.com"
    assert calls == [
        ("store_init", tmp_path / "accounts.sqlite3"),
        ("get_mail_account", "user@example.com"),
        ("mark_started", "user@example.com"),
        ("create_mail_provider", "auto"),
        ("provider_init", None),
        ("prime_inbox", "user@example.com"),
        ("browser_init", None),
        ("browser_enter", None),
        ("machine_init", ANY),
        ("open_chatgpt", None),
        ("complete_registration", ("user@example.com", "user@example.com", "pw", 30)),
        ("browser_exit", None),
        ("verify_registered_account", "user@example.com"),
        ("mark_succeeded", "user@example.com"),
    ]


def test_run_register_marks_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[tuple[str, object]] = []
    for env_var in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        monkeypatch.delenv(env_var, raising=False)

    class FakeStore:
        def __init__(self, db_path: Path) -> None:
            self.db_path = db_path

        def get_mail_account(self, email: str) -> MailAccountRecord:
            return MailAccountRecord(
                email=email,
                mail_client_id="client-id",
                mail_refresh_token="mail-refresh-token",
            )

        def mark_registration_started(self, email: str) -> None:
            calls.append(("mark_started", email))

        def mark_registration_succeeded(self, email: str) -> None:
            calls.append(("mark_succeeded", email))

        def mark_registration_failed(self, email: str, error_message: str) -> None:
            calls.append(("mark_failed", (email, error_message)))

    class FakeBrowser:
        def __init__(self, *, proxy: str | None, logger: object | None = None) -> None:
            return None

        async def __aenter__(self) -> FakeBrowser:
            return self

        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

        async def open_chatgpt(self) -> None:
            return None

        async def capture_debug_artifacts(self, label: str) -> None:
            calls.append(("capture_debug_artifacts", label))

    class FakeMachine:
        def __init__(self, *, browser: FakeBrowser, code_provider: object) -> None:
            return None

        async def complete_registration(
            self,
            *,
            account: MailAccountRecord,
            email: str,
            password: str,
            timeout: int,
        ) -> str:
            raise RuntimeError("verification timed out")

    class FakeProvider:
        def __init__(self, *, proxy: str | None) -> None:
            return None

        async def prime_inbox(self, *, account: MailAccountRecord) -> None:
            calls.append(("prime_inbox", account.email))

    def fake_create_mail_provider(
        account: object,
        *,
        provider_choice: str = "auto",
        proxy: str | None = None,
    ) -> FakeProvider:
        return FakeProvider(proxy=proxy)

    async def fake_verify_registered_account(**kwargs: object) -> None:
        calls.append(("verify_registered_account", kwargs["email"]))

    monkeypatch.setattr(cli, "RegistrationAccountStore", FakeStore)
    monkeypatch.setattr(cli, "PatchrightBrowser", FakeBrowser)
    monkeypatch.setattr(cli, "RegistrationStateMachine", FakeMachine)
    monkeypatch.setattr(cli, "create_mail_provider", fake_create_mail_provider)
    monkeypatch.setattr(cli, "verify_registered_account", fake_verify_registered_account)

    with pytest.raises(RuntimeError, match="verification timed out"):
        cli.asyncio.run(
            cli.run_register(
                email="user@example.com",
                password="pw",
                db_path=str(tmp_path / "accounts.sqlite3"),
                timeout=30,
                proxy=None,
                callback_port=1455,
                artifacts_dir=str(tmp_path / "logs"),
            )
        )

    assert calls == [
        ("mark_started", "user@example.com"),
        ("prime_inbox", "user@example.com"),
        ("capture_debug_artifacts", "register-failure"),
        ("mark_failed", ("user@example.com", "verification timed out")),
    ]


def test_run_register_marks_failure_when_post_registration_verification_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[tuple[str, object]] = []
    for env_var in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        monkeypatch.delenv(env_var, raising=False)

    class FakeStore:
        def __init__(self, db_path: Path) -> None:
            self.db_path = db_path

        def get_mail_account(self, email: str) -> MailAccountRecord:
            return MailAccountRecord(
                email=email,
                mail_client_id="client-id",
                mail_refresh_token="mail-refresh-token",
            )

        def mark_registration_started(self, email: str) -> None:
            calls.append(("mark_started", email))

        def mark_registration_succeeded(self, email: str) -> None:
            calls.append(("mark_succeeded", email))

        def mark_registration_failed(self, email: str, error_message: str) -> None:
            calls.append(("mark_failed", (email, error_message)))

    class FakeBrowser:
        def __init__(self, *, proxy: str | None, logger: object | None = None) -> None:
            return None

        async def __aenter__(self) -> FakeBrowser:
            return self

        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

        async def open_chatgpt(self) -> None:
            return None

        async def capture_debug_artifacts(self, label: str) -> None:
            calls.append(("capture_debug_artifacts", label))

    class FakeMachine:
        def __init__(self, *, browser: FakeBrowser, code_provider: object, logger: object | None = None) -> None:
            return None

        async def complete_registration(
            self,
            *,
            account: MailAccountRecord,
            email: str,
            password: str,
            timeout: int,
        ) -> str:
            return "success"

    class FakeProvider:
        def __init__(self, *, proxy: str | None) -> None:
            return None

        async def prime_inbox(self, *, account: MailAccountRecord) -> None:
            calls.append(("prime_inbox", account.email))

    def fake_create_mail_provider(
        account: object,
        *,
        provider_choice: str = "auto",
        proxy: str | None = None,
    ) -> FakeProvider:
        return FakeProvider(proxy=proxy)

    async def fake_verify_registered_account(**kwargs: object) -> None:
        raise RuntimeError("strict login verification failed")

    monkeypatch.setattr(cli, "RegistrationAccountStore", FakeStore)
    monkeypatch.setattr(cli, "PatchrightBrowser", FakeBrowser)
    monkeypatch.setattr(cli, "RegistrationStateMachine", FakeMachine)
    monkeypatch.setattr(cli, "create_mail_provider", fake_create_mail_provider)
    monkeypatch.setattr(cli, "verify_registered_account", fake_verify_registered_account)

    with pytest.raises(RuntimeError, match="strict login verification failed"):
        cli.asyncio.run(
            cli.run_register(
                email="user@example.com",
                password="pw",
                db_path=str(tmp_path / "accounts.sqlite3"),
                timeout=30,
                proxy=None,
                callback_port=1455,
                artifacts_dir=str(tmp_path / "logs"),
            )
        )

    assert calls == [
        ("mark_started", "user@example.com"),
        ("prime_inbox", "user@example.com"),
        ("capture_debug_artifacts", "register-failure"),
        ("mark_failed", ("user@example.com", "strict login verification failed")),
    ]
