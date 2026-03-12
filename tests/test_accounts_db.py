from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import cast

import pytest

import openai_oauth_cli.accounts_db as accounts_db
from openai_oauth_cli.accounts_db import AccountStore, ImportStats


def _fetch_one(db_path: Path, sql: str, params: tuple[object, ...] = ()) -> sqlite3.Row:
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(sql, params).fetchone()
    assert row is not None
    return row


def _fetch_all(db_path: Path, sql: str, params: tuple[object, ...] = ()) -> list[sqlite3.Row]:
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        return list(connection.execute(sql, params).fetchall())


def _execute(db_path: Path, sql: str, params: tuple[object, ...] = ()) -> None:
    with sqlite3.connect(db_path) as connection:
        connection.execute(sql, params)
        connection.commit()


def test_resolve_account_update_promotes_registered_when_primary_enabled() -> None:
    row = {
        "group_name": "group-a",
        "is_registered": 0,
        "is_primary": 0,
    }

    resolved = accounts_db._resolve_account_update(
        row,
        group_name=None,
        is_registered=None,
        is_primary=True,
        updated_at="2026-03-12T00:00:00+00:00",
    )

    assert resolved.group_name == "group-a"
    assert resolved.is_registered is True
    assert resolved.is_primary is True
    assert resolved.updated_at == "2026-03-12T00:00:00+00:00"


def test_resolve_account_update_clears_primary_when_registration_disabled() -> None:
    row = {
        "group_name": "group-a",
        "is_registered": 1,
        "is_primary": 1,
    }

    resolved = accounts_db._resolve_account_update(
        row,
        group_name="ops",
        is_registered=False,
        is_primary=None,
        updated_at="2026-03-12T00:00:00+00:00",
    )

    assert resolved.group_name == "ops"
    assert resolved.is_registered is False
    assert resolved.is_primary is False


def test_init_db_creates_required_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "accounts.sqlite3"

    store = AccountStore(db_path)
    store.init_db()

    assert store.table_exists("accounts") is True
    assert store.table_exists("source_files") is True
    assert store.table_exists("account_sources") is True

    columns = {
        str(row["name"]): row
        for row in _fetch_all(db_path, "PRAGMA table_info(accounts)")
    }
    assert {"email", "mail_client_id", "mail_refresh_token", "group_name", "is_registered", "is_primary"} <= set(
        columns
    )
    assert columns["email"]["notnull"] == 1
    assert columns["mail_client_id"]["notnull"] == 1
    assert columns["mail_refresh_token"]["notnull"] == 1
    assert columns["is_registered"]["notnull"] == 1
    assert columns["is_registered"]["dflt_value"] == "0"
    assert columns["is_primary"]["notnull"] == 1
    assert columns["is_primary"]["dflt_value"] == "0"

    source_file_columns = {
        str(row["name"]): row
        for row in _fetch_all(db_path, "PRAGMA table_info(source_files)")
    }
    assert {"source_name", "source_path", "source_sha256", "imported_at"} <= set(source_file_columns)
    assert source_file_columns["source_name"]["notnull"] == 1
    assert source_file_columns["source_path"]["notnull"] == 1
    assert source_file_columns["source_sha256"]["notnull"] == 1
    assert source_file_columns["imported_at"]["notnull"] == 1

    account_source_columns = {
        str(row["name"]): row
        for row in _fetch_all(db_path, "PRAGMA table_info(account_sources)")
    }
    assert {"account_id", "source_file_id", "source_group_name", "source_row_number", "raw_line"} <= set(
        account_source_columns
    )
    assert account_source_columns["account_id"]["notnull"] == 1
    assert account_source_columns["source_file_id"]["notnull"] == 1
    assert account_source_columns["source_group_name"]["notnull"] == 1
    assert account_source_columns["source_row_number"]["notnull"] == 1
    assert account_source_columns["raw_line"]["notnull"] == 1

    foreign_keys = {
        (str(row["from"]), str(row["table"]), str(row["to"]))
        for row in _fetch_all(db_path, "PRAGMA foreign_key_list(account_sources)")
    }
    assert ("account_id", "accounts", "id") in foreign_keys
    assert ("source_file_id", "source_files", "id") in foreign_keys

    index_rows = _fetch_all(db_path, "PRAGMA index_list(account_sources)")
    unique_indexes = [str(row["name"]) for row in index_rows if row["unique"] == 1]
    unique_index_columns = [
        [str(index_row["name"]) for index_row in _fetch_all(db_path, f"PRAGMA index_info({index_name!r})")]
        for index_name in unique_indexes
    ]
    assert ["source_file_id", "source_row_number"] in unique_index_columns


def test_import_txt_file_preserves_refresh_token_suffix_and_tracks_source_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "accounts.sqlite3"
    txt_path = tmp_path / "accounts.txt"
    raw_line = "a@example.com----pw----uuid-1----mail-rt$$----x----default"
    txt_path.write_text(raw_line + "\n", encoding="utf-8")

    store = AccountStore(db_path)
    store.init_db()
    store.import_txt_file(txt_path)

    account_row = _fetch_one(
        db_path,
        """
        SELECT email, mail_client_id, mail_refresh_token, group_name, is_registered, is_primary
        FROM accounts
        WHERE lower(email) = lower(?)
        """,
        ("a@example.com",),
    )
    assert account_row["mail_client_id"] == "uuid-1"
    assert account_row["mail_refresh_token"] == "mail-rt$$"
    assert account_row["mail_refresh_token"].endswith("$$")
    assert account_row["group_name"] == "default"
    assert account_row["is_registered"] == 0
    assert account_row["is_primary"] == 0

    source_file_row = _fetch_one(
        db_path,
        "SELECT source_name, source_path, source_sha256 FROM source_files",
    )
    assert source_file_row["source_name"] == txt_path.name
    assert source_file_row["source_path"] == str(txt_path)
    assert re.fullmatch(r"[0-9a-f]{64}", source_file_row["source_sha256"])

    source_row = _fetch_one(
        db_path,
        """
        SELECT source_group_name, source_row_number, raw_line
        FROM account_sources
        """,
    )
    assert source_row["source_group_name"] == "default"
    assert source_row["source_row_number"] == 1
    assert source_row["raw_line"] == raw_line


def test_find_account_by_email_reads_from_sqlite_store(tmp_path: Path) -> None:
    db_path = tmp_path / "accounts.sqlite3"
    txt_path = tmp_path / "accounts.txt"
    txt_path.write_text(
        "joann@example.com----pw----uuid-joann----rt-joann----x----Codex Team2\n",
        encoding="utf-8",
    )

    store = AccountStore(db_path)
    store.init_db()
    store.import_txt_file(txt_path)

    account = store.find_account_by_email("  JOANN@EXAMPLE.COM  ")

    assert account.email == "joann@example.com"
    assert account.mail_client_id == "uuid-joann"
    assert account.mail_refresh_token == "rt-joann"
    assert account.group == "Codex Team2"
    assert account.is_registered is False
    assert account.is_primary is False


def test_get_account_email_by_id_returns_email(tmp_path: Path) -> None:
    db_path = tmp_path / "accounts.sqlite3"
    txt_path = tmp_path / "accounts.txt"
    txt_path.write_text(
        "user@example.com----pw----uuid-user----rt-user----x----group-a\n",
        encoding="utf-8",
    )

    store = AccountStore(db_path)
    store.init_db()
    store.import_txt_file(txt_path)

    account_id = int(_fetch_one(db_path, "SELECT id FROM accounts WHERE lower(email) = lower(?)", ("user@example.com",))["id"])

    assert store.get_account_email_by_id(account_id) == "user@example.com"


def test_import_txt_file_skips_rows_with_blank_required_fields(tmp_path: Path) -> None:
    db_path = tmp_path / "accounts.sqlite3"
    txt_path = tmp_path / "accounts.txt"
    txt_path.write_text(
        "\n".join(
            [
                "valid@example.com----pw----uuid-valid----rt-valid----x----default",
                "   ----pw----uuid-blank-email----rt-blank-email----x----default",
                "blank-client@example.com----pw----   ----rt-blank-client----x----default",
                "blank-refresh@example.com----pw----uuid-blank-refresh----   ----x----default",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    store = AccountStore(db_path)
    store.init_db()
    store.import_txt_file(txt_path)

    rows = _fetch_all(
        db_path,
        "SELECT email, mail_client_id, mail_refresh_token FROM accounts ORDER BY lower(email)",
    )

    assert [(row["email"], row["mail_client_id"], row["mail_refresh_token"]) for row in rows] == [
        ("valid@example.com", "uuid-valid", "rt-valid")
    ]


def test_account_sources_foreign_keys_are_enforced_at_runtime(tmp_path: Path) -> None:
    db_path = tmp_path / "accounts.sqlite3"
    txt_path = tmp_path / "accounts.txt"
    txt_path.write_text(
        "a@example.com----pw----uuid-1----mail-rt$$----x----default\n",
        encoding="utf-8",
    )

    store = AccountStore(db_path)
    store.init_db()
    store.import_txt_file(txt_path)

    account_row = _fetch_one(db_path, "SELECT id FROM accounts WHERE lower(email) = lower(?)", ("a@example.com",))
    source_file_row = _fetch_one(db_path, "SELECT id FROM source_files")

    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO account_sources (account_id, source_file_id, source_group_name, source_row_number, raw_line)
                VALUES (?, ?, ?, ?, ?)
                """,
                (999999, source_file_row["id"], "default", 2, "missing-account"),
            )

    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO account_sources (account_id, source_file_id, source_group_name, source_row_number, raw_line)
                VALUES (?, ?, ?, ?, ?)
                """,
                (account_row["id"], 999999, "default", 2, "missing-source-file"),
            )


def test_import_txt_file_inserts_new_accounts_with_sqlite_state_defaults(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "accounts.sqlite3"
    txt_path = tmp_path / "accounts.txt"
    txt_path.write_text(
        "\n".join(
            [
                "drake@example.com----pw----uuid-drake----rt-drake----x----gpt team 1",
                "joann@example.com----pw----uuid-joann----rt-joann----x----Codex Team2",
                "patience@example.com----pw----uuid-patience----rt-patience----x----gpt team 1",
                "kyler@example.com----pw----uuid-kyler----rt-kyler----x----Codex Team2",
                "garrett@example.com----pw----uuid-garrett----rt-garrett----x----默认分组",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    store = AccountStore(db_path)
    store.init_db()
    store.import_txt_file(txt_path)

    rows = _fetch_all(
        db_path,
        "SELECT email, is_registered, is_primary FROM accounts ORDER BY lower(email)",
    )
    status_by_email = {
        str(row["email"]).strip().casefold(): (row["is_registered"], row["is_primary"])
        for row in rows
    }

    assert status_by_email["drake@example.com"] == (0, 0)
    assert status_by_email["joann@example.com"] == (0, 0)
    assert status_by_email["patience@example.com"] == (0, 0)
    assert status_by_email["kyler@example.com"] == (0, 0)
    assert status_by_email["garrett@example.com"] == (0, 0)


def test_import_txt_file_does_not_derive_state_from_group_name(tmp_path: Path) -> None:
    db_path = tmp_path / "accounts.sqlite3"
    txt_path = tmp_path / "accounts.txt"
    txt_path.write_text(
        "\n".join(
            [
                "sofia@example.com----pw----uuid-sofia----rt-sofia----x----gpt team 1",
                "brand-new@example.com----pw----uuid-brand-new----rt-brand-new----x----gpt team 1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    store = AccountStore(db_path)
    store.init_db()
    store.import_txt_file(txt_path)

    rows = _fetch_all(
        db_path,
        "SELECT email, is_registered, is_primary FROM accounts ORDER BY lower(email)",
    )
    status_by_email = {
        str(row["email"]).strip().casefold(): (row["is_registered"], row["is_primary"])
        for row in rows
    }

    assert status_by_email["sofia@example.com"] == (0, 0)
    assert status_by_email["brand-new@example.com"] == (0, 0)


def test_import_txt_file_does_not_reseed_user_managed_flags_after_first_insert(tmp_path: Path) -> None:
    db_path = tmp_path / "accounts.sqlite3"
    first_path = tmp_path / "accounts-first.txt"
    second_path = tmp_path / "accounts-second.txt"
    first_path.write_text(
        "\n".join(
            [
                "joann@example.com----pw----uuid-joann-1----rt-joann-1----x----Codex Team2",
                "patience@example.com----pw----uuid-patience-1----rt-patience-1----x----gpt team 1",
                "garrett@example.com----pw----uuid-garrett-1----rt-garrett-1----x----默认分组",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    second_path.write_text(
        "\n".join(
            [
                "joann@example.com----pw----uuid-joann-2----rt-joann-2----x----Codex Team2",
                "patience@example.com----pw----uuid-patience-2----rt-patience-2----x----gpt team 1",
                "garrett@example.com----pw----uuid-garrett-2----rt-garrett-2----x----默认分组",
                "sofia@example.com----pw----uuid-sofia-2----rt-sofia-2----x----gpt team 1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    store = AccountStore(db_path)
    store.init_db()
    store.import_txt_file(first_path)

    _execute(
        db_path,
        """
        UPDATE accounts
        SET is_registered = ?, is_primary = ?
        WHERE lower(email) = lower(?)
        """,
        (1, 0, "joann@example.com"),
    )
    _execute(
        db_path,
        """
        UPDATE accounts
        SET is_registered = ?, is_primary = ?
        WHERE lower(email) = lower(?)
        """,
        (0, 0, "patience@example.com"),
    )
    _execute(
        db_path,
        """
        UPDATE accounts
        SET is_registered = ?, is_primary = ?
        WHERE lower(email) = lower(?)
        """,
        (1, 0, "garrett@example.com"),
    )

    store.import_txt_file(second_path)

    rows = _fetch_all(
        db_path,
        """
        SELECT email, mail_client_id, mail_refresh_token, is_registered, is_primary
        FROM accounts
        ORDER BY lower(email)
        """,
    )
    accounts_by_email = {str(row["email"]).strip().casefold(): row for row in rows}

    assert accounts_by_email["joann@example.com"]["mail_client_id"] == "uuid-joann-2"
    assert accounts_by_email["joann@example.com"]["mail_refresh_token"] == "rt-joann-2"
    assert (
        accounts_by_email["joann@example.com"]["is_registered"],
        accounts_by_email["joann@example.com"]["is_primary"],
    ) == (1, 0)

    assert accounts_by_email["patience@example.com"]["mail_client_id"] == "uuid-patience-2"
    assert accounts_by_email["patience@example.com"]["mail_refresh_token"] == "rt-patience-2"
    assert (
        accounts_by_email["patience@example.com"]["is_registered"],
        accounts_by_email["patience@example.com"]["is_primary"],
    ) == (0, 0)

    assert accounts_by_email["garrett@example.com"]["mail_client_id"] == "uuid-garrett-2"
    assert accounts_by_email["garrett@example.com"]["mail_refresh_token"] == "rt-garrett-2"
    assert (
        accounts_by_email["garrett@example.com"]["is_registered"],
        accounts_by_email["garrett@example.com"]["is_primary"],
    ) == (1, 0)

    assert accounts_by_email["sofia@example.com"]["mail_client_id"] == "uuid-sofia-2"
    assert accounts_by_email["sofia@example.com"]["mail_refresh_token"] == "rt-sofia-2"
    assert (
        accounts_by_email["sofia@example.com"]["is_registered"],
        accounts_by_email["sofia@example.com"]["is_primary"],
    ) == (0, 0)


def test_import_txt_files_applies_multiple_sources_in_order(tmp_path: Path) -> None:
    db_path = tmp_path / "accounts.sqlite3"
    first_path = tmp_path / "accounts-first.txt"
    second_path = tmp_path / "accounts-second.txt"
    first_path.write_text(
        "\n".join(
            [
                "first@example.com----pw----uuid-first-1----rt-first-1----x----默认分组",
                "shared@example.com----pw----uuid-shared-1----rt-shared-1----x----默认分组",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    second_path.write_text(
        "\n".join(
            [
                "second@example.com----pw----uuid-second-2----rt-second-2----x----team 3",
                "shared@example.com----pw----uuid-shared-2----rt-shared-2----x----team 3",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    store = AccountStore(db_path)
    store.init_db()
    stats = store.import_txt_files([first_path, second_path])

    rows = _fetch_all(
        db_path,
        """
        SELECT email, mail_client_id, mail_refresh_token, group_name, is_registered, is_primary
        FROM accounts
        ORDER BY lower(email)
        """,
    )
    accounts_by_email = {str(row["email"]).strip().casefold(): row for row in rows}

    assert stats.imported == 4
    assert stats.skipped == 0
    assert accounts_by_email["first@example.com"]["mail_client_id"] == "uuid-first-1"
    assert accounts_by_email["second@example.com"]["mail_client_id"] == "uuid-second-2"
    assert accounts_by_email["shared@example.com"]["mail_client_id"] == "uuid-shared-2"
    assert accounts_by_email["shared@example.com"]["mail_refresh_token"] == "rt-shared-2"
    assert accounts_by_email["shared@example.com"]["group_name"] == "默认分组"
    assert (
        accounts_by_email["shared@example.com"]["is_registered"],
        accounts_by_email["shared@example.com"]["is_primary"],
    ) == (0, 0)




def test_import_txt_file_keeps_sqlite_owned_group_name_on_reimport(tmp_path: Path) -> None:
    db_path = tmp_path / "accounts.sqlite3"
    first_path = tmp_path / "accounts-first.txt"
    second_path = tmp_path / "accounts-second.txt"
    first_path.write_text(
        "shared@example.com----pw----uuid-shared-1----rt-shared-1----x----default\n",
        encoding="utf-8",
    )
    second_path.write_text(
        "shared@example.com----pw----uuid-shared-2----rt-shared-2----x----team 3\n",
        encoding="utf-8",
    )

    store = AccountStore(db_path)
    store.init_db()
    store.import_txt_file(first_path)
    _execute(
        db_path,
        "UPDATE accounts SET group_name = ?, updated_at = ? WHERE lower(email) = lower(?)",
        ("sqlite-owned", "2026-03-11T00:00:00+00:00", "shared@example.com"),
    )

    store.import_txt_file(second_path)

    row = _fetch_one(
        db_path,
        "SELECT mail_client_id, mail_refresh_token, group_name FROM accounts WHERE lower(email) = lower(?)",
        ("shared@example.com",),
    )
    source_rows = _fetch_all(
        db_path,
        "SELECT source_group_name FROM account_sources ORDER BY source_row_number, id",
    )

    assert row["mail_client_id"] == "uuid-shared-2"
    assert row["mail_refresh_token"] == "rt-shared-2"
    assert row["group_name"] == "sqlite-owned"
    assert [str(source_row["source_group_name"]) for source_row in source_rows] == ["default", "team 3"]


def test_list_accounts_filters_and_pages_results(tmp_path: Path) -> None:
    db_path = tmp_path / "accounts.sqlite3"
    txt_path = tmp_path / "accounts.txt"
    txt_path.write_text(
        "\n".join(
            [
                "alpha@example.com----pw----uuid-alpha----rt-alpha----x----group-a",
                "bravo@example.com----pw----uuid-bravo----rt-bravo----x----group-b",
                "charlie@example.com----pw----uuid-charlie----rt-charlie----x----group-a",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    store = AccountStore(db_path)
    store.init_db()
    store.import_txt_file(txt_path)
    _execute(
        db_path,
        "UPDATE accounts SET is_registered = 1, is_primary = 1 WHERE lower(email) = lower(?)",
        ("charlie@example.com",),
    )

    assert hasattr(store, "list_accounts")
    page = store.list_accounts(query="a", group_name="group-a", is_registered=True, limit=1, offset=0)
    items = cast(list[dict[str, object]], page["items"])

    assert page["total"] == 1
    assert page["limit"] == 1
    assert page["offset"] == 0
    assert [item["email"] for item in items] == ["charlie@example.com"]
    assert items[0]["is_primary"] is True


def test_update_account_enforces_primary_requires_registered(tmp_path: Path) -> None:
    db_path = tmp_path / "accounts.sqlite3"
    txt_path = tmp_path / "accounts.txt"
    txt_path.write_text(
        "user@example.com----pw----uuid-user----rt-user----x----default\n",
        encoding="utf-8",
    )

    store = AccountStore(db_path)
    store.init_db()
    store.import_txt_file(txt_path)

    assert hasattr(store, "update_account")
    updated = store.update_account(
        "user@example.com",
        group_name="ops",
        is_primary=True,
    )

    assert updated["group_name"] == "ops"
    assert updated["is_registered"] is True
    assert updated["is_primary"] is True

    updated = store.update_account("user@example.com", is_registered=False)

    assert updated["is_registered"] is False
    assert updated["is_primary"] is False


def test_bulk_update_accounts_updates_target_rows_only(tmp_path: Path) -> None:
    db_path = tmp_path / "accounts.sqlite3"
    txt_path = tmp_path / "accounts.txt"
    txt_path.write_text(
        "\n".join(
            [
                "first@example.com----pw----uuid-first----rt-first----x----default",
                "second@example.com----pw----uuid-second----rt-second----x----default",
                "third@example.com----pw----uuid-third----rt-third----x----default",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    store = AccountStore(db_path)
    store.init_db()
    store.import_txt_file(txt_path)

    assert hasattr(store, "bulk_update_accounts")
    updated_count = store.bulk_update_accounts(
        emails=["first@example.com", "third@example.com"],
        group_name="batch-group",
        is_registered=True,
    )

    rows = _fetch_all(
        db_path,
        "SELECT email, group_name, is_registered, is_primary FROM accounts ORDER BY lower(email)",
    )

    assert updated_count == 2
    assert [(row["email"], row["group_name"], row["is_registered"], row["is_primary"]) for row in rows] == [
        ("first@example.com", "batch-group", 1, 0),
        ("second@example.com", "default", 0, 0),
        ("third@example.com", "batch-group", 1, 0),
    ]


def test_bulk_update_accounts_uses_one_timestamp_for_the_batch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "accounts.sqlite3"
    txt_path = tmp_path / "accounts.txt"
    txt_path.write_text(
        "\n".join(
            [
                "first@example.com----pw----uuid-first----rt-first----x----default",
                "second@example.com----pw----uuid-second----rt-second----x----default",
                "third@example.com----pw----uuid-third----rt-third----x----default",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    store = AccountStore(db_path)
    store.init_db()
    store.import_txt_file(txt_path)

    timestamps = iter(
        [
            "2026-03-12T10:00:00+00:00",
            "2026-03-12T10:00:01+00:00",
            "2026-03-12T10:00:02+00:00",
        ]
    )
    monkeypatch.setattr(accounts_db, "_utcnow", lambda: next(timestamps))

    updated_count = store.bulk_update_accounts(
        emails=["first@example.com", "third@example.com"],
        group_name="batch-group",
        is_registered=True,
    )

    rows = _fetch_all(
        db_path,
        """
        SELECT email, updated_at
        FROM accounts
        WHERE lower(email) IN (lower(?), lower(?))
        ORDER BY lower(email)
        """,
        ("first@example.com", "third@example.com"),
    )

    assert updated_count == 2
    assert [row["updated_at"] for row in rows] == [
        "2026-03-12T10:00:00+00:00",
        "2026-03-12T10:00:00+00:00",
    ]


def test_bulk_update_accounts_is_atomic_when_one_email_is_missing(tmp_path: Path) -> None:
    db_path = tmp_path / "accounts.sqlite3"
    txt_path = tmp_path / "accounts.txt"
    txt_path.write_text(
        "\n".join(
            [
                "first@example.com----pw----uuid-first----rt-first----x----default",
                "second@example.com----pw----uuid-second----rt-second----x----default",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    store = AccountStore(db_path)
    store.init_db()
    store.import_txt_file(txt_path)

    with pytest.raises(ValueError, match="account not found"):
        store.bulk_update_accounts(
            emails=["first@example.com", "missing@example.com"],
            group_name="batch-group",
            is_registered=True,
        )

    rows = _fetch_all(
        db_path,
        "SELECT email, group_name, is_registered, is_primary FROM accounts ORDER BY lower(email)",
    )

    assert [(row["email"], row["group_name"], row["is_registered"], row["is_primary"]) for row in rows] == [
        ("first@example.com", "default", 0, 0),
        ("second@example.com", "default", 0, 0),
    ]


def test_bulk_update_accounts_deduplicates_normalized_emails(tmp_path: Path) -> None:
    db_path = tmp_path / "accounts.sqlite3"
    txt_path = tmp_path / "accounts.txt"
    txt_path.write_text(
        "\n".join(
            [
                "first@example.com----pw----uuid-first----rt-first----x----default",
                "second@example.com----pw----uuid-second----rt-second----x----default",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    store = AccountStore(db_path)
    store.init_db()
    store.import_txt_file(txt_path)

    updated_count = store.bulk_update_accounts(
        emails=[" First@Example.com ", "first@example.com", "SECOND@example.com"],
        group_name="batch-group",
        is_primary=True,
    )

    rows = _fetch_all(
        db_path,
        "SELECT email, group_name, is_registered, is_primary FROM accounts ORDER BY lower(email)",
    )

    assert updated_count == 2
    assert [(row["email"], row["group_name"], row["is_registered"], row["is_primary"]) for row in rows] == [
        ("first@example.com", "batch-group", 1, 1),
        ("second@example.com", "batch-group", 1, 1),
    ]


def test_get_summary_reports_registration_and_primary_counts(tmp_path: Path) -> None:
    db_path = tmp_path / "accounts.sqlite3"
    txt_path = tmp_path / "accounts.txt"
    txt_path.write_text(
        "\n".join(
            [
                "first@example.com----pw----uuid-first----rt-first----x----group-a",
                "second@example.com----pw----uuid-second----rt-second----x----group-a",
                "third@example.com----pw----uuid-third----rt-third----x----group-b",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    store = AccountStore(db_path)
    store.init_db()
    store.import_txt_file(txt_path)
    _execute(
        db_path,
        "UPDATE accounts SET is_registered = 1, is_primary = CASE WHEN lower(email) = lower(?) THEN 1 ELSE 0 END WHERE lower(email) IN (lower(?), lower(?))",
        ("third@example.com", "first@example.com", "third@example.com"),
    )

    assert hasattr(store, "get_summary")
    summary = store.get_summary()

    assert summary == {
        "accounts": 3,
        "registered": 2,
        "primary": 1,
        "groups": {"group-a": 2, "group-b": 1},
    }


def test_export_accounts_returns_filtered_json_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "accounts.sqlite3"
    txt_path = tmp_path / "accounts.txt"
    txt_path.write_text(
        "\n".join(
            [
                "first@example.com----pw----uuid-first----rt-first----x----group-a",
                "second@example.com----pw----uuid-second----rt-second----x----group-b",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    store = AccountStore(db_path)
    store.init_db()
    store.import_txt_file(txt_path)

    assert hasattr(store, "export_accounts")
    payload = json.loads(store.export_accounts(format="json", group_name="group-b"))

    assert payload == [
        {
            "email": "second@example.com",
            "group_name": "group-b",
            "is_primary": False,
            "is_registered": False,
            "updated_at": payload[0]["updated_at"],
        }
    ]


def test_import_text_sources_supports_in_memory_uploads(tmp_path: Path) -> None:
    db_path = tmp_path / "accounts.sqlite3"
    store = AccountStore(db_path)
    store.init_db()

    assert hasattr(store, "import_text_sources")
    assert hasattr(accounts_db, "ImportTextSource")
    stats = store.import_text_sources(
        [
            accounts_db.ImportTextSource(
                source_name="upload-1.txt",
                source_path="upload://upload-1.txt",
                text="upload@example.com----pw----uuid-upload----rt-upload----x----uploads\n",
            )
        ]
    )
    empty_stats = store.import_text_sources([])

    account = store.find_account_by_email("upload@example.com")
    source_file = _fetch_one(
        db_path,
        "SELECT source_name, source_path FROM source_files WHERE source_name = ?",
        ("upload-1.txt",),
    )

    assert stats == ImportStats(imported=1, skipped=0)
    assert empty_stats == ImportStats(imported=0, skipped=0)
    assert account.group == "uploads"
    assert source_file["source_path"] == "upload://upload-1.txt"
