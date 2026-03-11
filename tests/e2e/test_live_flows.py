from __future__ import annotations

from dataclasses import dataclass
import os
import shutil
import sqlite3
from pathlib import Path

import pytest

from openai_register import cli as register_cli


REGISTERED_EMAIL_ENV_VAR = "OPENAI_E2E_REGISTERED_EMAIL"
UNREGISTERED_VERIFY_EMAIL_ENV_VAR = "OPENAI_E2E_UNREGISTERED_VERIFY_EMAIL"
UNREGISTERED_REGISTER_EMAIL_ENV_VAR = "OPENAI_E2E_UNREGISTERED_REGISTER_EMAIL"
TIMEOUT_ENV_VAR = "OPENAI_E2E_TIMEOUT"
PROXY_ENV_VAR = "OPENAI_E2E_PROXY"
CALLBACK_PORT_ENV_VAR = "OPENAI_E2E_CALLBACK_PORT"
ARTIFACTS_DIR_ENV_VAR = "OPENAI_E2E_ARTIFACTS_DIR"


@dataclass(frozen=True)
class LiveE2EAccounts:
    registered_email: str
    unregistered_verify_email: str
    unregistered_register_email: str


def _create_accounts_db(path: Path, rows: list[tuple[str, int]]) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE accounts (
                email TEXT NOT NULL PRIMARY KEY,
                mail_client_id TEXT NOT NULL,
                mail_refresh_token TEXT NOT NULL,
                is_registered INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO accounts (email, mail_client_id, mail_refresh_token, is_registered)
            VALUES (?, 'client-id', 'mail-refresh-token', ?)
            """,
            rows,
        )


def test_copy_database_for_live_e2e_creates_isolated_temp_file(tmp_path: Path) -> None:
    source_db = tmp_path / "source.sqlite3"
    _create_accounts_db(source_db, [("registered@example.com", 1)])

    copied_db = copy_database_for_live_e2e(source_db=source_db, temp_dir=tmp_path / "run")

    assert copied_db != source_db
    assert copied_db.is_file()

    with sqlite3.connect(copied_db) as connection:
        connection.execute("DELETE FROM accounts WHERE email = 'registered@example.com'")
        connection.commit()

    with sqlite3.connect(source_db) as connection:
        count = connection.execute("SELECT COUNT(*) FROM accounts").fetchone()

    assert count == (1,)


def test_select_live_e2e_accounts_prefers_explicit_overrides(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db_path = tmp_path / "accounts.sqlite3"
    _create_accounts_db(
        db_path,
        [
            ("registered@example.com", 1),
            ("verify-unregistered@example.com", 0),
            ("register-unregistered@example.com", 0),
        ],
    )
    monkeypatch.setenv("OPENAI_E2E_REGISTERED_EMAIL", "registered@example.com")
    monkeypatch.setenv("OPENAI_E2E_UNREGISTERED_VERIFY_EMAIL", "verify-unregistered@example.com")
    monkeypatch.setenv("OPENAI_E2E_UNREGISTERED_REGISTER_EMAIL", "register-unregistered@example.com")

    accounts = select_live_e2e_accounts(db_path)

    assert accounts.registered_email == "registered@example.com"
    assert accounts.unregistered_verify_email == "verify-unregistered@example.com"
    assert accounts.unregistered_register_email == "register-unregistered@example.com"


def normalize_email(email: str) -> str:
    return email.strip().casefold()


def copy_database_for_live_e2e(*, source_db: Path, temp_dir: Path) -> Path:
    temp_dir.mkdir(parents=True, exist_ok=True)
    copied_db = temp_dir / source_db.name
    shutil.copy2(source_db, copied_db)
    return copied_db


def _load_accounts(db_path: Path) -> list[tuple[str, bool]]:
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            "SELECT email, is_registered FROM accounts ORDER BY lower(email), email"
        ).fetchall()
    return [(str(email), bool(is_registered)) for email, is_registered in rows]


def _resolve_override(name: str, accounts: list[tuple[str, bool]], *, registered: bool) -> str | None:
    override = os.getenv(name, "").strip()
    if not override:
        return None
    normalized_override = normalize_email(override)
    for email, is_registered in accounts:
        if normalize_email(email) == normalized_override and is_registered is registered:
            return email
    raise ValueError(f"{name} did not match a {'registered' if registered else 'unregistered'} account: {override}")


def select_live_e2e_accounts(db_path: Path) -> LiveE2EAccounts:
    accounts = _load_accounts(db_path)

    registered_override = _resolve_override(REGISTERED_EMAIL_ENV_VAR, accounts, registered=True)
    verify_override = _resolve_override(UNREGISTERED_VERIFY_EMAIL_ENV_VAR, accounts, registered=False)
    register_override = _resolve_override(UNREGISTERED_REGISTER_EMAIL_ENV_VAR, accounts, registered=False)

    registered_accounts = [email for email, is_registered in accounts if is_registered]
    unregistered_accounts = [email for email, is_registered in accounts if not is_registered]

    registered_email = registered_override or registered_accounts[0]

    chosen_unregistered: list[str] = []
    if verify_override:
        chosen_unregistered.append(verify_override)
    if register_override and normalize_email(register_override) not in {normalize_email(email) for email in chosen_unregistered}:
        chosen_unregistered.append(register_override)

    for email in unregistered_accounts:
        if normalize_email(email) in {normalize_email(selected) for selected in chosen_unregistered}:
            continue
        chosen_unregistered.append(email)
        if len(chosen_unregistered) == 2:
            break

    if len(chosen_unregistered) < 2:
        raise ValueError("need two distinct unregistered accounts for live E2E scenarios")

    return LiveE2EAccounts(
        registered_email=registered_email,
        unregistered_verify_email=chosen_unregistered[0],
        unregistered_register_email=chosen_unregistered[1],
    )


@pytest.fixture
def copied_e2e_db(live_e2e_db_path: Path, tmp_path: Path) -> Path:
    return copy_database_for_live_e2e(source_db=live_e2e_db_path, temp_dir=tmp_path / "db-copy")


@pytest.fixture
def live_e2e_accounts(copied_e2e_db: Path) -> LiveE2EAccounts:
    try:
        return select_live_e2e_accounts(copied_e2e_db)
    except ValueError as exc:
        if any(
            os.getenv(name, "").strip()
            for name in (
                REGISTERED_EMAIL_ENV_VAR,
                UNREGISTERED_VERIFY_EMAIL_ENV_VAR,
                UNREGISTERED_REGISTER_EMAIL_ENV_VAR,
            )
        ):
            pytest.fail(str(exc))
        pytest.skip(str(exc))


@pytest.fixture
def live_e2e_artifacts_dir(tmp_path: Path) -> Path:
    override = os.getenv(ARTIFACTS_DIR_ENV_VAR, "").strip()
    if override:
        path = Path(override).expanduser()
    else:
        path = tmp_path / "artifacts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _build_cli_args(*, command: str, email: str, db_path: Path, artifacts_dir: Path | None = None) -> list[str]:
    args = [command, "--email", email, "--db-path", str(db_path)]
    timeout = os.getenv(TIMEOUT_ENV_VAR, "").strip()
    if timeout:
        args.extend(["--timeout", timeout])
    proxy = os.getenv(PROXY_ENV_VAR, "").strip()
    if proxy:
        args.extend(["--proxy", proxy])
    callback_port = os.getenv(CALLBACK_PORT_ENV_VAR, "").strip()
    if callback_port:
        args.extend(["--callback-port", callback_port])
    if artifacts_dir is not None:
        args.extend(["--artifacts-dir", str(artifacts_dir)])
    return args


def _read_registration_state(db_path: Path, email: str) -> tuple[int, str | None, str]:
    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT is_registered, registered_at, last_registration_error
            FROM accounts
            WHERE email = ? COLLATE NOCASE
            """,
            (email,),
        ).fetchone()
    if row is None:
        raise AssertionError(f"account not found in copied db: {email}")
    return int(row[0]), row[1], str(row[2] or "")


@pytest.mark.live_e2e
def test_live_verify_login_succeeds_for_registered_account(
    live_e2e_enabled: bool,
    copied_e2e_db: Path,
    live_e2e_accounts: LiveE2EAccounts,
    live_e2e_artifacts_dir: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    del live_e2e_enabled
    email = live_e2e_accounts.registered_email

    exit_code = register_cli.main(
        _build_cli_args(
            command="verify-login",
            email=email,
            db_path=copied_e2e_db,
            artifacts_dir=live_e2e_artifacts_dir,
        )
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip() == f"verified:{email}"
    assert captured.err == ""


@pytest.mark.live_e2e
def test_live_verify_login_fails_for_unregistered_account(
    live_e2e_enabled: bool,
    copied_e2e_db: Path,
    live_e2e_accounts: LiveE2EAccounts,
    live_e2e_artifacts_dir: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    del live_e2e_enabled
    email = live_e2e_accounts.unregistered_verify_email

    exit_code = register_cli.main(
        _build_cli_args(
            command="verify-login",
            email=email,
            db_path=copied_e2e_db,
            artifacts_dir=live_e2e_artifacts_dir,
        )
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "incorrect email address or password" in captured.err


@pytest.mark.live_e2e
def test_live_register_then_verify_login_succeeds(
    live_e2e_enabled: bool,
    copied_e2e_db: Path,
    live_e2e_accounts: LiveE2EAccounts,
    live_e2e_artifacts_dir: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    del live_e2e_enabled
    email = live_e2e_accounts.unregistered_register_email

    register_exit = register_cli.main(
        _build_cli_args(
            command="register",
            email=email,
            db_path=copied_e2e_db,
            artifacts_dir=live_e2e_artifacts_dir,
        )
    )
    register_output = capsys.readouterr()

    assert register_exit == 0
    assert register_output.out.strip() == f"registered:{email}"
    assert register_output.err == ""

    is_registered, registered_at, last_registration_error = _read_registration_state(copied_e2e_db, email)
    assert is_registered == 1
    assert registered_at
    assert last_registration_error == ""

    verify_exit = register_cli.main(
        _build_cli_args(
            command="verify-login",
            email=email,
            db_path=copied_e2e_db,
            artifacts_dir=live_e2e_artifacts_dir,
        )
    )
    verify_output = capsys.readouterr()

    assert verify_exit == 0
    assert verify_output.out.strip() == f"verified:{email}"
    assert verify_output.err == ""
