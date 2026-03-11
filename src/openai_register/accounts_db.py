from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from openai_auth_core.accounts_db import (
    connect_sqlite,
    ensure_accounts_table,
    ensure_registration_columns,
    normalize_email,
)

from .models import MailAccountRecord, RegistrationAccountRecord


class RegistrationAccountStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.ensure_registration_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = connect_sqlite(self.db_path, require_existing=True)
        ensure_accounts_table(connection)
        return connection

    def ensure_registration_schema(self) -> None:
        with self._connect() as connection:
            ensure_registration_columns(connection)
            connection.commit()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def get_account(self, email: str) -> RegistrationAccountRecord:
        normalized = normalize_email(email)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    email,
                    mail_client_id,
                    mail_refresh_token,
                    is_registered,
                    registered_at,
                    last_registration_attempt_at,
                    last_registration_error
                FROM accounts
                WHERE email_normalized = ?
                """,
                (normalized,),
            ).fetchone()
        if row is None:
            raise ValueError(f"account not found for email: {email}")
        return RegistrationAccountRecord(
            email=str(row["email"]),
            mail_client_id=str(row["mail_client_id"]),
            mail_refresh_token=str(row["mail_refresh_token"]),
            is_registered=bool(row["is_registered"]),
            registered_at=row["registered_at"],
            last_registration_attempt_at=row["last_registration_attempt_at"],
            last_registration_error=str(row["last_registration_error"] or ""),
        )

    def get_mail_account(self, email: str) -> MailAccountRecord:
        account = self.get_account(email)
        return MailAccountRecord(
            email=account.email,
            mail_client_id=account.mail_client_id,
            mail_refresh_token=account.mail_refresh_token,
        )

    def mark_registration_started(self, email: str) -> None:
        self._update_account(
            email,
            """
            UPDATE accounts
            SET last_registration_attempt_at = ?
            WHERE email_normalized = ?
            """,
            (self._now(), normalize_email(email)),
        )

    def mark_registration_succeeded(self, email: str) -> None:
        now = self._now()
        self._update_account(
            email,
            """
            UPDATE accounts
            SET
                is_registered = 1,
                registered_at = CASE
                    WHEN registered_at IS NULL OR registered_at = '' THEN ?
                    ELSE registered_at
                END,
                last_registration_error = ''
            WHERE email_normalized = ?
            """,
            (now, normalize_email(email)),
        )

    def mark_registration_failed(self, email: str, error_message: str) -> None:
        self._update_account(
            email,
            """
            UPDATE accounts
            SET last_registration_error = ?
            WHERE email_normalized = ?
            """,
            (error_message, normalize_email(email)),
        )

    def _update_account(self, email: str, sql: str, params: tuple[str, ...]) -> None:
        with self._connect() as connection:
            cursor = connection.execute(sql, params)
            if cursor.rowcount == 0:
                raise ValueError(f"account not found for email: {email}")
            connection.commit()
