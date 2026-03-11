from __future__ import annotations

from pathlib import Path
import sqlite3


REGISTRATION_COLUMNS: dict[str, str] = {
    "email_normalized": "TEXT NOT NULL DEFAULT ''",
    "registered_at": "TEXT",
    "last_registration_attempt_at": "TEXT",
    "last_registration_error": "TEXT NOT NULL DEFAULT ''",
}


def connect_sqlite(
    db_path: Path,
    *,
    create_parent: bool = False,
    require_existing: bool = False,
) -> sqlite3.Connection:
    resolved_path = Path(db_path)
    if require_existing and not resolved_path.exists():
        raise FileNotFoundError(f"database file does not exist: {resolved_path}")
    if create_parent:
        resolved_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(resolved_path)
    connection.row_factory = sqlite3.Row
    return connection


def normalize_email(email: str) -> str:
    return email.strip().casefold()


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def tables_exist(connection: sqlite3.Connection, *table_names: str) -> bool:
    if not table_names:
        return True
    placeholders = ", ".join("?" for _ in table_names)
    rows = connection.execute(
        f"SELECT name FROM sqlite_master WHERE type = 'table' AND name IN ({placeholders})",
        table_names,
    ).fetchall()
    return {str(row["name"]) for row in rows} == set(table_names)


def ensure_accounts_table(connection: sqlite3.Connection) -> None:
    if not table_exists(connection, "accounts"):
        raise RuntimeError("accounts table is missing")


def ensure_registration_columns(connection: sqlite3.Connection) -> None:
    connection.create_function("CASEFOLD", 1, lambda value: None if value is None else str(value).casefold(), deterministic=True)
    column_rows = connection.execute("PRAGMA table_info(accounts)").fetchall()
    existing = {str(row["name"]) for row in column_rows}
    for column_name, column_type in REGISTRATION_COLUMNS.items():
        if column_name in existing:
            continue
        connection.execute(f"ALTER TABLE accounts ADD COLUMN {column_name} {column_type}")
    connection.execute(
        """
        UPDATE accounts
        SET email_normalized = CASEFOLD(trim(email))
        WHERE email_normalized = ''
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_accounts_email_normalized
        ON accounts(email_normalized)
        """
    )
