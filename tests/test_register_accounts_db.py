from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, cast

import pytest

from openai_register import accounts_db as register_accounts_db
from openai_register.accounts_db import RegistrationAccountStore


def _create_db(path: Path, *, email: str = "user@example.com") -> None:
    connection = sqlite3.connect(path)
    try:
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
        connection.execute(
            """
            INSERT INTO accounts (email, mail_client_id, mail_refresh_token, is_registered)
            VALUES (?, ?, ?, ?)
            """,
            (email, "client-id", "mail-refresh-token", 0),
        )
        connection.commit()
    finally:
        connection.close()


def test_mark_registration_started_updates_attempt_time(tmp_path: Path) -> None:
    db_path = tmp_path / "accounts.sqlite3"
    _create_db(db_path)
    store = RegistrationAccountStore(db_path)

    store.mark_registration_started("user@example.com")
    account = store.get_account("user@example.com")

    assert account.last_registration_attempt_at
    assert account.is_registered is False


def test_mark_registration_succeeded_sets_registered_fields(tmp_path: Path) -> None:
    db_path = tmp_path / "accounts.sqlite3"
    _create_db(db_path)
    store = RegistrationAccountStore(db_path)

    store.mark_registration_started("user@example.com")
    store.mark_registration_succeeded("user@example.com")
    account = store.get_account("user@example.com")

    assert account.is_registered is True
    assert account.registered_at
    assert account.last_registration_error == ""


def test_mark_registration_failed_updates_last_error_only(tmp_path: Path) -> None:
    db_path = tmp_path / "accounts.sqlite3"
    _create_db(db_path)
    store = RegistrationAccountStore(db_path)

    store.mark_registration_failed("user@example.com", "verification code timed out")
    account = store.get_account("user@example.com")

    assert account.is_registered is False
    assert account.last_registration_error == "verification code timed out"


def test_get_account_requires_existing_email(tmp_path: Path) -> None:
    db_path = tmp_path / "accounts.sqlite3"
    _create_db(db_path)
    store = RegistrationAccountStore(db_path)

    with pytest.raises(ValueError, match="account not found"):
        store.get_account("missing@example.com")


def test_get_account_normalizes_unicode_email_case(tmp_path: Path) -> None:
    db_path = tmp_path / "accounts.sqlite3"
    _create_db(db_path, email="JÖRG@example.com")
    store = RegistrationAccountStore(db_path)

    account = store.get_account("  jörg@example.com  ")

    assert account.email == "JÖRG@example.com"


def test_ensure_registration_schema_adds_missing_columns(tmp_path: Path) -> None:
    db_path = tmp_path / "accounts.sqlite3"
    _create_db(db_path)
    store = RegistrationAccountStore(db_path)

    store.ensure_registration_schema()

    with sqlite3.connect(db_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(accounts)").fetchall()}

    assert {"email_normalized", "registered_at", "last_registration_attempt_at", "last_registration_error"} <= columns


def test_get_account_uses_index_friendly_lookup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db_path = tmp_path / "accounts.sqlite3"
    _create_db(db_path, email="JÖRG@example.com")
    executed_sql: list[str] = []
    real_connect = sqlite3.connect

    class RecordingConnection(sqlite3.Connection):
        def execute(self, sql: str, parameters: Any = ()) -> sqlite3.Cursor:
            executed_sql.append(" ".join(sql.split()))
            return super().execute(sql, parameters)

    def connect(path: str | Path, *args: Any, **kwargs: Any) -> sqlite3.Connection:
        kwargs.setdefault("factory", RecordingConnection)
        return cast(sqlite3.Connection, real_connect(path, *args, **kwargs))

    monkeypatch.setattr(register_accounts_db.sqlite3, "connect", connect)

    store = RegistrationAccountStore(db_path)
    store.ensure_registration_schema()
    executed_sql.clear()

    account = store.get_account("  jörg@example.com  ")

    assert account.email == "JÖRG@example.com"
    assert any("WHERE email_normalized = ?" in sql for sql in executed_sql)
    assert not any("WHERE CASEFOLD(trim(email)) = ?" in sql for sql in executed_sql)
