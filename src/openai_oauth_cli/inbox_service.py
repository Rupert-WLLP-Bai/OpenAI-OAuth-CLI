from __future__ import annotations

from typing import Any, TypedDict

import aiohttp

from openai_auth_core.mailbox import create_mail_provider, extract_verification_code, _html_to_text

from .accounts_db import AccountStore


class InboxMessage(TypedDict):
    id: str
    subject: str
    from_address: str
    received_at: str
    body_preview: str
    body_text: str
    verification_code: str | None


def _normalize_message(message: dict[str, Any]) -> InboxMessage:
    body_preview = str(message.get("body_preview", "") or "")
    body_html = str(message.get("body_html", "") or "")
    body_text = _html_to_text(body_html) if body_html else _html_to_text(body_preview)

    return {
        "id": str(message.get("id", "") or ""),
        "subject": str(message.get("subject", "") or ""),
        "from_address": str(message.get("from_address", "") or ""),
        "received_at": str(message.get("received_at", "") or ""),
        "body_preview": body_preview,
        "body_text": body_text,
        "verification_code": extract_verification_code(body_text),
    }


class InboxService:
    def __init__(self, store: AccountStore, *, proxy: str | None = None) -> None:
        self.store = store
        self.proxy = proxy

    async def fetch_inbox(self, email: str) -> dict[str, object]:
        account = self.store.find_account_by_email(email)
        provider = create_mail_provider(account, provider_choice="auto", proxy=self.proxy)
        timeout = aiohttp.ClientTimeout(total=30)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                messages = await provider.fetch_messages(session, account)
        except Exception as exc:
            raise RuntimeError(f"failed to fetch inbox for {account.email}: {exc}") from exc

        return {
            "account": {
                "email": account.email,
                "group_name": account.group,
                "is_registered": account.is_registered,
                "is_primary": account.is_primary,
            },
            "messages": [_normalize_message(message) for message in messages],
        }
