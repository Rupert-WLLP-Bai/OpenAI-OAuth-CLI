from __future__ import annotations

import html
import re
from typing import Any

import aiohttp

from openai_auth_core.mailbox import Wyx66Provider

from .accounts_db import AccountStore


_SCRIPT_STYLE_RE = re.compile(r"(?is)<(script|style).*?>.*?</\1>")
_TAG_RE = re.compile(r"(?s)<[^>]+>")
_WHITESPACE_RE = re.compile(r"[ \t\r\f\v]+")


def _html_to_text(value: str) -> str:
    if not value:
        return ""
    text = _SCRIPT_STYLE_RE.sub(" ", value)
    text = re.sub(r"(?i)<br\\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p\\s*>", "\n", text)
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    text = _WHITESPACE_RE.sub(" ", text)
    text = re.sub(r" *\n *", "\n", text)
    return text.strip()


def _normalize_message(message: dict[str, Any]) -> dict[str, str]:
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
    }


class InboxService:
    def __init__(self, store: AccountStore, *, proxy: str | None = None) -> None:
        self.store = store
        self.proxy = proxy

    async def fetch_inbox(self, email: str) -> dict[str, object]:
        account = self.store.find_account_by_email(email)
        provider = Wyx66Provider(proxy=self.proxy)
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
