from __future__ import annotations

from pathlib import Path
from typing import Iterable, Protocol

from openai_auth_core.mailbox import (
    GRAPH_API_BASE,
    GraphApiProvider,
    MAIL_POLL_INTERVAL_SECONDS,
    WYX66_API_BASE,
    Wyx66Provider,
    create_mail_provider,
    extract_verification_code,
)

from .models import AccountRecord


DEFAULT_PASSWORD = "C.WLLP159357"
DEFAULT_ACCOUNTS_FILE = Path(__file__).resolve().parents[2] / "secrets" / "openai_mail_accounts_2026-03-10.txt"


class VerificationCodeProvider(Protocol):
    async def get_code(self, *, account: AccountRecord, timeout: int) -> str | None: ...


def normalize_email(email: str) -> str:
    return email.strip().casefold()


def parse_accounts_text(text: str) -> list[AccountRecord]:
    accounts: list[AccountRecord] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split("----")
        if len(parts) < 6:
            continue
        accounts.append(
            AccountRecord(
                email=parts[0].strip(),
                mail_client_id=parts[2].strip(),
                mail_refresh_token=parts[3].strip(),
                group=parts[5].strip(),
            )
        )
    return accounts


def load_accounts_file(path: Path = DEFAULT_ACCOUNTS_FILE) -> list[AccountRecord]:
    return parse_accounts_text(path.read_text(encoding="utf-8"))


def find_account_by_email(accounts: Iterable[AccountRecord], email: str) -> AccountRecord:
    normalized = normalize_email(email)
    matches = [account for account in accounts if normalize_email(account.email) == normalized]
    if not matches:
        raise ValueError(f"account not found for email: {email}")
    if len(matches) > 1:
        raise ValueError(f"multiple accounts found for email: {email}")
    return matches[0]


__all__ = [
    "DEFAULT_ACCOUNTS_FILE",
    "DEFAULT_PASSWORD",
    "GRAPH_API_BASE",
    "GraphApiProvider",
    "MAIL_POLL_INTERVAL_SECONDS",
    "VerificationCodeProvider",
    "WYX66_API_BASE",
    "Wyx66Provider",
    "create_mail_provider",
    "extract_verification_code",
    "find_account_by_email",
    "load_accounts_file",
    "normalize_email",
    "parse_accounts_text",
]
