from __future__ import annotations

import asyncio
import html
import json
import re
from typing import Any, Iterable, Literal, Protocol

import aiohttp


WYX66_API_BASE = "https://app.wyx66.com"
MAIL_POLL_INTERVAL_SECONDS = 3

# Microsoft Graph API constants
MS_TOKEN_ENDPOINTS = [
    "https://login.microsoftonline.com/common/oauth2/v2.0/token",
    "https://login.microsoftonline.com/consumers/oauth2/v2.0/token",
]
MS_TOKEN_SCOPE = "https://graph.microsoft.com/Mail.Read offline_access"
GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
RECENT_MESSAGE_THRESHOLD_SECONDS = 60

# HTML to text conversion patterns
_SCRIPT_STYLE_RE = re.compile(r"(?is)<(script|style).*?>.*?</\1>")
_TAG_RE = re.compile(r"(?s)<[^>]+>")
_WHITESPACE_RE = re.compile(r"[ \t\r\f\v]+")


def _html_to_text(value: str) -> str:
    """Convert HTML to plain text, stripping tags and normalizing whitespace."""
    if not value:
        return ""
    text = _SCRIPT_STYLE_RE.sub(" ", value)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p\s*>", "\n", text)
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    text = _WHITESPACE_RE.sub(" ", text)
    text = re.sub(r" *\n *", "\n", text)
    return text.strip()


class MailAccountLike(Protocol):
    email: str
    mail_client_id: str
    mail_refresh_token: str


def extract_verification_code(text: str) -> str | None:
    if not text:
        return None

    # First try context-specific patterns
    context_patterns = (
        r"code[\s:]+(\d{6})",
        r"verification code[\s:]+(\d{6})",
        r"验证码[\s:]+(\d{6})",
        r"Your code is[\s:]+(\d{6})",
        r"enter this code[\s:]+(\d{6})",
    )
    for pattern in context_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)

    # Fallback: find any 6-digit number, but exclude color codes
    for match in re.finditer(r"\b(\d{6})\b", text):
        code = match.group(1)
        # Check context around the match
        start = max(0, match.start() - 10)
        end = min(len(text), match.end() + 10)
        context = text[start:end]

        # Skip if it looks like a color code (#XXXXXX)
        if f"#{code}" in context:
            continue
        # Skip CSS color patterns
        if re.search(r"color[:\s]*[^;]*" + code, context, re.IGNORECASE):
            continue
        # Skip if preceded by # or rgb/rgba/hsl
        if re.search(r"[#]|rgb|rgba|hsl", context[:15], re.IGNORECASE):
            continue

        return code

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


def _select_verification_code(
    messages: Iterable[dict[str, Any]],
    checked_ids: set[str],
    *,
    use_time_filter: bool = False,
) -> str | None:
    for message in messages:
        message_id = str(message.get("id", "")).strip()
        if message_id and message_id in checked_ids:
            continue
        if message_id:
            checked_ids.add(message_id)
        if use_time_filter and not _is_recent_message(message):
            continue
        if not _is_openai_verification_message(message):
            continue

        # Convert HTML to text first, then extract code
        body_html = str(message.get("body_html", "") or "")
        body_preview = str(message.get("body_preview", "") or "")
        body_text = _html_to_text(body_html) if body_html else _html_to_text(body_preview)

        if code := extract_verification_code(body_text):
            return code
    return None


def _normalize_refresh_token(token: str) -> str:
    """Strip trailing $ characters from refresh token (compatibility for certain tools)."""
    return token.rstrip("$").strip()


def _is_recent_message(
    message: dict[str, Any],
    threshold_seconds: int = RECENT_MESSAGE_THRESHOLD_SECONDS,
) -> bool:
    """Check if message was received within the threshold."""
    from datetime import datetime, timezone

    received_at = message.get("received_at", "")
    if not received_at:
        return True  # No timestamp, assume recent
    try:
        # ISO 8601 format: 2024-01-15T10:30:00Z
        dt_str = received_at[:19]
        dt = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S")
        # Assume UTC if timezone info is missing
        if received_at.endswith("Z") or "+" not in received_at:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        age_seconds = (now - dt).total_seconds()
        return age_seconds < threshold_seconds
    except (ValueError, TypeError):
        return True  # Parse error, assume recent


def _normalize_graph_message(msg: dict[str, Any]) -> dict[str, Any]:
    """Convert Graph API message format to internal format."""
    return {
        "id": msg.get("id", ""),
        "subject": msg.get("subject", ""),
        "from_address": msg.get("from", {}).get("emailAddress", {}).get("address", ""),
        "received_at": msg.get("receivedDateTime", ""),
        "body_preview": msg.get("bodyPreview", ""),
        "body_html": msg.get("body", {}).get("content", ""),
    }


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


class GraphApiProvider:
    """
    Mail provider using Microsoft Graph API directly.

    Requires:
    - mail_client_id: Microsoft application client ID
    - mail_refresh_token: OAuth2 refresh token with Mail.Read scope
    """

    def __init__(self, *, proxy: str | None = None) -> None:
        self.proxy = proxy
        self._checked_ids_by_email: dict[str, set[str]] = {}
        self._access_tokens: dict[str, str] = {}

    @staticmethod
    def _account_key(email: str) -> str:
        return email.strip().casefold()

    async def _get_access_token(self, session: aiohttp.ClientSession, account: MailAccountLike) -> str:
        """Exchange refresh token for access token, trying both endpoints."""
        refresh_token = _normalize_refresh_token(account.mail_refresh_token)
        errors: list[str] = []

        for endpoint in MS_TOKEN_ENDPOINTS:
            body = {
                "client_id": account.mail_client_id,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
                "scope": MS_TOKEN_SCOPE,
            }
            async with session.post(
                endpoint,
                data=body,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                proxy=self.proxy,
            ) as response:
                resp_text = await response.text()
                if response.status == 200:
                    data = json.loads(resp_text)
                    access_token = data.get("access_token", "")
                    if access_token:
                        return str(access_token)
                errors.append(f"{endpoint}: {response.status}")

        raise RuntimeError(f"Failed to refresh access token from all endpoints: {'; '.join(errors)}")

    async def fetch_messages(self, session: aiohttp.ClientSession, account: MailAccountLike) -> list[dict[str, Any]]:
        """Fetch messages from Graph API and normalize to internal format."""
        account_key = self._account_key(account.email)

        # Get or refresh access token
        access_token = self._access_tokens.get(account_key)
        if not access_token:
            access_token = await self._get_access_token(session, account)
            self._access_tokens[account_key] = access_token

        # Build query params
        params = {
            "$top": "50",
            "$orderby": "receivedDateTime desc",
            "$select": "id,subject,from,receivedDateTime,bodyPreview,body",
        }

        async with session.get(
            f"{GRAPH_API_BASE}/me/messages",
            params=params,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            proxy=self.proxy,
        ) as response:
            if response.status == 401:
                # Token expired, refresh and retry once
                self._access_tokens.pop(account_key, None)
                access_token = await self._get_access_token(session, account)
                self._access_tokens[account_key] = access_token
                # Retry with new token
                async with session.get(
                    f"{GRAPH_API_BASE}/me/messages",
                    params=params,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                    proxy=self.proxy,
                ) as retry_response:
                    if retry_response.status != 200:
                        body = await retry_response.text()
                        raise RuntimeError(f"Graph API error {retry_response.status}: {body[:200]}")
                    data = json.loads(await retry_response.text())
            elif response.status != 200:
                body = await response.text()
                raise RuntimeError(f"Graph API error {response.status}: {body[:200]}")
            else:
                data = json.loads(await response.text())

        messages = data.get("value", [])
        return [_normalize_graph_message(msg) for msg in messages]

    async def prime_inbox(self, *, account: MailAccountLike) -> None:
        client_timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=client_timeout) as session:
            messages = await self.fetch_messages(session, account)
        checked_ids = {msg.get("id", "") for msg in messages if msg.get("id")}
        self._checked_ids_by_email[self._account_key(account.email)] = checked_ids

    async def get_code(self, *, account: MailAccountLike, timeout: int) -> str | None:
        checked_ids = set(self._checked_ids_by_email.get(self._account_key(account.email), set()))
        deadline = asyncio.get_running_loop().time() + timeout
        client_timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=client_timeout) as session:
            while asyncio.get_running_loop().time() < deadline:
                messages = await self.fetch_messages(session, account)
                if code := _select_verification_code(messages, checked_ids, use_time_filter=True):
                    self._checked_ids_by_email[self._account_key(account.email)] = checked_ids
                    return code
                remaining_seconds = deadline - asyncio.get_running_loop().time()
                if remaining_seconds <= 0:
                    break
                await asyncio.sleep(min(MAIL_POLL_INTERVAL_SECONDS, remaining_seconds))
        self._checked_ids_by_email[self._account_key(account.email)] = checked_ids
        return None


def create_mail_provider(
    account: MailAccountLike,
    *,
    provider_choice: Literal["auto", "graph", "wyx66"] = "auto",
    proxy: str | None = None,
) -> Wyx66Provider | GraphApiProvider:
    """
    Create a mail provider based on account and user choice.

    Auto-detection logic:
    - Microsoft refresh_token typically starts with "M.C"
    """
    if provider_choice == "graph":
        return GraphApiProvider(proxy=proxy)
    elif provider_choice == "wyx66":
        return Wyx66Provider(proxy=proxy)
    else:  # auto
        if account.mail_refresh_token.startswith("M.C"):
            return GraphApiProvider(proxy=proxy)
        return Wyx66Provider(proxy=proxy)
