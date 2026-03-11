from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Iterable, Protocol

import aiohttp


WYX66_API_BASE = "https://app.wyx66.com"
MAIL_POLL_INTERVAL_SECONDS = 3


class MailAccountLike(Protocol):
    email: str
    mail_client_id: str
    mail_refresh_token: str


def extract_verification_code(text: str) -> str | None:
    if not text:
        return None
    patterns = (
        r"\b(\d{6})\b",
        r"code[\s:]+(\d{6})",
        r"verification code[\s:]+(\d{6})",
        r"验证码[\s:]+(\d{6})",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _is_openai_verification_message(message: dict[str, Any]) -> bool:
    subject = str(message.get("subject", "")).casefold()
    from_address = str(message.get("from_address", "")).casefold()
    return (
        "openai" in from_address
        or "chatgpt" in from_address
        or "openai" in subject
        or "verification" in subject
    )


def _select_verification_code(messages: Iterable[dict[str, Any]], checked_ids: set[str]) -> str | None:
    for message in messages:
        message_id = str(message.get("id", "")).strip()
        if message_id and message_id in checked_ids:
            continue
        if message_id:
            checked_ids.add(message_id)
        if not _is_openai_verification_message(message):
            continue
        body = str(message.get("body_html", "") or message.get("body_preview", ""))
        if code := extract_verification_code(body):
            return code
    return None


class Wyx66Provider:
    def __init__(self, *, api_base: str = WYX66_API_BASE, proxy: str | None = None) -> None:
        self.api_base = api_base.rstrip("/")
        self.proxy = proxy
        self._checked_ids_by_email: dict[str, set[str]] = {}

    @staticmethod
    def _account_key(email: str) -> str:
        return email.strip().casefold()

    async def fetch_messages(self, session: aiohttp.ClientSession, account: MailAccountLike) -> list[dict[str, Any]]:
        payload = {
            "email_address": account.email,
            "client_id": account.mail_client_id,
            "refresh_token": account.mail_refresh_token,
            "folder": "inbox",
            "token_type": "o2",
        }
        async with session.post(
            f"{self.api_base}/api/emails/refresh",
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Referer": f"{self.api_base}/",
                "Origin": self.api_base,
            },
            proxy=self.proxy,
        ) as response:
            body = await response.text()
            if response.status != 200:
                raise RuntimeError(f"wyx66 request failed with status {response.status}: {body[:200]}")
            data = json.loads(body)
            if not data.get("success"):
                raise RuntimeError(f"wyx66 request did not succeed: {body[:200]}")
            return list(data.get("data", []))

    async def prime_inbox(self, *, account: MailAccountLike) -> None:
        client_timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=client_timeout) as session:
            messages = await self.fetch_messages(session, account)
        checked_ids = {
            str(message.get("id", "")).strip()
            for message in messages
            if str(message.get("id", "")).strip()
        }
        self._checked_ids_by_email[self._account_key(account.email)] = checked_ids

    async def get_code(self, *, account: MailAccountLike, timeout: int) -> str | None:
        checked_ids = set(self._checked_ids_by_email.get(self._account_key(account.email), set()))
        deadline = asyncio.get_running_loop().time() + timeout
        client_timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=client_timeout) as session:
            while asyncio.get_running_loop().time() < deadline:
                messages = await self.fetch_messages(session, account)
                if code := _select_verification_code(messages, checked_ids):
                    self._checked_ids_by_email[self._account_key(account.email)] = checked_ids
                    return code
                remaining_seconds = deadline - asyncio.get_running_loop().time()
                if remaining_seconds <= 0:
                    break
                await asyncio.sleep(min(MAIL_POLL_INTERVAL_SECONDS, remaining_seconds))
        self._checked_ids_by_email[self._account_key(account.email)] = checked_ids
        return None
