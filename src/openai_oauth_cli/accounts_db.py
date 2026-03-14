from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Iterable, Iterator

from openai_auth_core.accounts_db import connect_sqlite, table_exists as sqlite_table_exists, tables_exist as sqlite_tables_exist

from .mailbox import normalize_email, parse_accounts_text
from .models import AccountRecord


@dataclass(frozen=True)
class ImportStats:
    imported: int
    skipped: int


@dataclass(frozen=True)
class ImportTextSource:
    source_name: str
    source_path: str
    text: str


@dataclass(frozen=True)
class _ResolvedAccountUpdate:
    group_name: str
    is_registered: bool
    is_primary: bool
    updated_at: str


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _should_import_account(account: AccountRecord) -> bool:
    if not normalize_email(account.email):
        return False
    if not account.mail_client_id.strip():
        return False
    if not account.mail_refresh_token.strip():
        return False
    return True


def _resolve_account_update(
    row: Mapping[str, object],
    *,
    group_name: str | None = None,
    is_registered: bool | None = None,
    is_primary: bool | None = None,
    updated_at: str | None = None,
) -> _ResolvedAccountUpdate:
    next_group_name = str(row["group_name"]) if group_name is None else group_name
    next_is_registered = bool(row["is_registered"]) if is_registered is None else is_registered
    next_is_primary = bool(row["is_primary"]) if is_primary is None else is_primary

    if is_registered is False:
        next_is_primary = False
    if is_primary is True:
        next_is_registered = True
    if not next_is_registered:
        next_is_primary = False

    return _ResolvedAccountUpdate(
        group_name=next_group_name,
        is_registered=next_is_registered,
        is_primary=next_is_primary,
        updated_at=updated_at or _utcnow(),
    )


class AccountStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = connect_sqlite(self.db_path, create_parent=True)
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def init_db(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY,
                    email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    mail_client_id TEXT NOT NULL,
                    mail_refresh_token TEXT NOT NULL,
                    group_name TEXT NOT NULL DEFAULT '',
                    is_registered INTEGER NOT NULL DEFAULT 0 CHECK (is_registered IN (0, 1)),
                    is_primary INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0, 1)),
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    CHECK (is_primary = 0 OR is_registered = 1)
                );

                CREATE TABLE IF NOT EXISTS source_files (
                    id INTEGER PRIMARY KEY,
                    source_name TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    source_sha256 TEXT NOT NULL,
                    imported_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS account_sources (
                    id INTEGER PRIMARY KEY,
                    account_id INTEGER NOT NULL,
                    source_file_id INTEGER NOT NULL,
                    source_group_name TEXT NOT NULL DEFAULT '',
                    source_row_number INTEGER NOT NULL,
                    raw_line TEXT NOT NULL,
                    FOREIGN KEY (account_id) REFERENCES accounts(id),
                    FOREIGN KEY (source_file_id) REFERENCES source_files(id),
                    UNIQUE (source_file_id, source_row_number)
                );
                """
            )

    def table_exists(self, table_name: str) -> bool:
        with self._connect() as connection:
            return sqlite_table_exists(connection, table_name)

    def tables_exist(self, *table_names: str) -> bool:
        with self._connect() as connection:
            return sqlite_tables_exist(connection, *table_names)

    def get_account_email_by_id(self, account_id: int) -> str:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT email FROM accounts WHERE id = ?",
                (account_id,),
            ).fetchone()

        if row is None:
            raise ValueError(f"account not found for id: {account_id}")
        return str(row["email"])

    def import_txt_file(self, txt_path: Path) -> ImportStats:
        return self.import_txt_files([txt_path])

    def import_txt_files(self, txt_paths: Iterable[Path]) -> ImportStats:
        sources = [
            ImportTextSource(
                source_name=Path(txt_path).name,
                source_path=str(Path(txt_path)),
                text=Path(txt_path).read_text(encoding="utf-8"),
            )
            for txt_path in txt_paths
        ]
        return self.import_text_sources(sources)

    def import_text_sources(self, sources: Iterable[ImportTextSource]) -> ImportStats:
        imported = 0
        skipped = 0
        for source in sources:
            file_stats = self._import_text_source(source)
            imported += file_stats.imported
            skipped += file_stats.skipped
        return ImportStats(imported=imported, skipped=skipped)

    def _import_text_source(self, source: ImportTextSource) -> ImportStats:
        text = source.text
        imported_at = _utcnow()
        source_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
        imported = 0
        skipped = 0

        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO source_files (source_name, source_path, source_sha256, imported_at)
                VALUES (?, ?, ?, ?)
                """,
                (source.source_name, source.source_path, source_sha256, imported_at),
            )
            source_file_id = cursor.lastrowid
            assert source_file_id is not None

            for row_number, raw_line in enumerate(text.splitlines(), start=1):
                if not raw_line.strip():
                    continue
                parsed_accounts = parse_accounts_text(raw_line)
                if not parsed_accounts:
                    skipped += 1
                    continue

                account = parsed_accounts[0]
                if not _should_import_account(account):
                    skipped += 1
                    continue
                timestamp = _utcnow()
                connection.execute(
                    """
                    INSERT INTO accounts (
                        email,
                        mail_client_id,
                        mail_refresh_token,
                        group_name,
                        notes,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, '', ?, ?)
                    ON CONFLICT(email) DO UPDATE SET
                        email = excluded.email,
                        mail_client_id = excluded.mail_client_id,
                        mail_refresh_token = excluded.mail_refresh_token,
                        updated_at = excluded.updated_at
                    """,
                    (
                        account.email,
                        account.mail_client_id,
                        account.mail_refresh_token,
                        account.group,
                        timestamp,
                        timestamp,
                    ),
                )
                account_row = connection.execute(
                    "SELECT id FROM accounts WHERE email = ? COLLATE NOCASE",
                    (account.email,),
                ).fetchone()
                assert account_row is not None
                connection.execute(
                    """
                    INSERT INTO account_sources (
                        account_id,
                        source_file_id,
                        source_group_name,
                        source_row_number,
                        raw_line
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (account_row["id"], source_file_id, account.group, row_number, raw_line),
                )
                imported += 1

        return ImportStats(imported=imported, skipped=skipped)

    def list_accounts(
        self,
        *,
        query: str = "",
        group_name: str | None = None,
        is_registered: bool | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> dict[str, object]:
        where_clauses: list[str] = []
        params: list[object] = []

        normalized_query = query.strip()
        if normalized_query:
            where_clauses.append("lower(email) LIKE ?")
            params.append(f"%{normalized_query.casefold()}%")
        if group_name is not None:
            where_clauses.append("group_name = ?")
            params.append(group_name)
        if is_registered is not None:
            where_clauses.append("is_registered = ?")
            params.append(1 if is_registered else 0)

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        with self._connect() as connection:
            total_row = connection.execute(
                f"SELECT COUNT(*) AS count FROM accounts {where_sql}",
                tuple(params),
            ).fetchone()
            assert total_row is not None
            rows = connection.execute(
                f"""
                SELECT id, email, group_name, is_registered, is_primary, updated_at
                FROM accounts
                {where_sql}
                ORDER BY lower(email), email
                LIMIT ? OFFSET ?
                """,
                (*params, limit, offset),
            ).fetchall()

        return {
            "total": int(total_row["count"]),
            "limit": limit,
            "offset": offset,
            "items": [
                {
                    "id": int(row["id"]),
                    "email": str(row["email"]),
                    "group_name": str(row["group_name"]),
                    "is_registered": bool(row["is_registered"]),
                    "is_primary": bool(row["is_primary"]),
                    "updated_at": str(row["updated_at"]),
                }
                for row in rows
            ],
        }

    def update_account(
        self,
        email: str,
        *,
        group_name: str | None = None,
        is_registered: bool | None = None,
        is_primary: bool | None = None,
    ) -> dict[str, object]:
        normalized_email = normalize_email(email)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT email, group_name, is_registered, is_primary, updated_at
                FROM accounts
                WHERE email = ? COLLATE NOCASE
                """,
                (normalized_email,),
            ).fetchone()
            if row is None:
                raise ValueError(f"account not found for email: {email}")
            resolved = _resolve_account_update(
                row,
                group_name=group_name,
                is_registered=is_registered,
                is_primary=is_primary,
            )
            connection.execute(
                """
                UPDATE accounts
                SET group_name = ?, is_registered = ?, is_primary = ?, updated_at = ?
                WHERE email = ? COLLATE NOCASE
                """,
                (
                    resolved.group_name,
                    1 if resolved.is_registered else 0,
                    1 if resolved.is_primary else 0,
                    resolved.updated_at,
                    normalized_email,
                ),
            )

        return {
            "email": str(row["email"]),
            "group_name": resolved.group_name,
            "is_registered": resolved.is_registered,
            "is_primary": resolved.is_primary,
            "updated_at": resolved.updated_at,
        }

    def bulk_update_accounts(
        self,
        *,
        emails: Iterable[str],
        group_name: str | None = None,
        is_registered: bool | None = None,
        is_primary: bool | None = None,
    ) -> int:
        normalized_emails = list(dict.fromkeys(normalize_email(email) for email in emails))
        if not normalized_emails:
            return 0

        placeholders = ", ".join("?" for _ in normalized_emails)
        updated_at = _utcnow()
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT email, group_name, is_registered, is_primary
                FROM accounts
                WHERE lower(email) IN ({placeholders})
                """,
                tuple(normalized_emails),
            ).fetchall()

            rows_by_email = {normalize_email(str(row["email"])): row for row in rows}
            missing = [email for email in normalized_emails if email not in rows_by_email]
            if missing:
                raise ValueError(f"account not found for email: {missing[0]}")

            resolved_updates = [
                _resolve_account_update(
                    rows_by_email[normalized_email],
                    group_name=group_name,
                    is_registered=is_registered,
                    is_primary=is_primary,
                    updated_at=updated_at,
                )
                for normalized_email in normalized_emails
            ]

            connection.executemany(
                """
                UPDATE accounts
                SET group_name = ?, is_registered = ?, is_primary = ?, updated_at = ?
                WHERE email = ? COLLATE NOCASE
                """,
                [
                    (
                        resolved.group_name,
                        1 if resolved.is_registered else 0,
                        1 if resolved.is_primary else 0,
                        resolved.updated_at,
                        str(rows_by_email[normalized_email]["email"]),
                    )
                    for normalized_email, resolved in zip(normalized_emails, resolved_updates, strict=True)
                ],
            )

        return len(resolved_updates)

    def get_summary(self) -> dict[str, object]:
        with self._connect() as connection:
            totals = connection.execute(
                """
                SELECT
                    COUNT(*) AS accounts,
                    SUM(CASE WHEN is_registered = 1 THEN 1 ELSE 0 END) AS registered,
                    SUM(CASE WHEN is_primary = 1 THEN 1 ELSE 0 END) AS primary_accounts
                FROM accounts
                """
            ).fetchone()
            assert totals is not None
            group_rows = connection.execute(
                """
                SELECT group_name, COUNT(*) AS count
                FROM accounts
                GROUP BY group_name
                ORDER BY lower(group_name), group_name
                """
            ).fetchall()

        return {
            "accounts": int(totals["accounts"]),
            "registered": int(totals["registered"] or 0),
            "primary": int(totals["primary_accounts"] or 0),
            "groups": {str(row["group_name"]): int(row["count"]) for row in group_rows},
        }

    def export_accounts(self, *, format: str = "json", group_name: str | None = None) -> str:
        if format != "json":
            raise ValueError(f"unsupported export format: {format}")

        where_sql = ""
        params: tuple[object, ...] = ()
        if group_name is not None:
            where_sql = "WHERE group_name = ?"
            params = (group_name,)

        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT email, group_name, is_registered, is_primary, updated_at
                FROM accounts
                {where_sql}
                ORDER BY lower(email), email
                """,
                params,
            ).fetchall()

        payload = [
            {
                "email": str(row["email"]),
                "group_name": str(row["group_name"]),
                "is_registered": bool(row["is_registered"]),
                "is_primary": bool(row["is_primary"]),
                "updated_at": str(row["updated_at"]),
            }
            for row in rows
        ]
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

    def find_account_by_email(self, email: str) -> AccountRecord:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT email, mail_client_id, mail_refresh_token, group_name, is_registered, is_primary
                FROM accounts
                WHERE email = ? COLLATE NOCASE
                """,
                (normalize_email(email),),
            ).fetchone()

        if row is None:
            raise ValueError(f"account not found for email: {email}")

        return AccountRecord(
            email=str(row["email"]),
            mail_client_id=str(row["mail_client_id"]),
            mail_refresh_token=str(row["mail_refresh_token"]),
            group=str(row["group_name"]),
            is_registered=bool(row["is_registered"]),
            is_primary=bool(row["is_primary"]),
        )
