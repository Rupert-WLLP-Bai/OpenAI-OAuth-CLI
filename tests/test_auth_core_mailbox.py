from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import aiohttp

from openai_auth_core.mailbox import GraphApiProvider, MailAccountLike, Wyx66Provider


@dataclass(frozen=True)
class MailAccount:
    email: str
    mail_client_id: str
    mail_refresh_token: str


def test_auth_core_provider_ignores_codes_that_existed_before_prime() -> None:
    old_message = {
        "id": "old-message",
        "from_address": "noreply@openai.com",
        "subject": "OpenAI verification code",
        "body_preview": "Your code is 111111",
    }
    new_message = {
        "id": "new-message",
        "from_address": "noreply@openai.com",
        "subject": "OpenAI verification code",
        "body_preview": "Your code is 222222",
    }

    class StubProvider(Wyx66Provider):
        def __init__(self) -> None:
            super().__init__(api_base="https://example.invalid")
            self.responses = [[old_message], [old_message, new_message]]

        async def fetch_messages(self, session: aiohttp.ClientSession, account: MailAccountLike) -> list[dict[str, Any]]:
            return self.responses.pop(0)

    account = MailAccount(email="user@example.com", mail_client_id="client", mail_refresh_token="token")
    provider = StubProvider()

    async def run() -> str | None:
        await provider.prime_inbox(account=account)
        return await provider.get_code(account=account, timeout=1)

    assert asyncio.run(run()) == "222222"


def test_graph_api_provider_ignores_codes_that_existed_before_prime() -> None:
    """Test GraphApiProvider with stubbed fetch_messages."""
    from datetime import datetime, timezone

    # Use current time for messages (GraphApiProvider uses 60s time filter)
    now = datetime.now(timezone.utc)
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    old_message = {
        "id": "old-message",
        "from_address": "noreply@tm.openai.com",
        "subject": "Your OpenAI verification code",
        "body_preview": "Your verification code is 111111",
        "received_at": now_iso,
    }
    new_message = {
        "id": "new-message",
        "from_address": "noreply@tm.openai.com",
        "subject": "Your OpenAI verification code",
        "body_preview": "Your verification code is 333333",
        "received_at": now_iso,
    }

    class StubGraphProvider(GraphApiProvider):
        def __init__(self) -> None:
            super().__init__()
            self.responses = [[old_message], [old_message, new_message]]

        async def fetch_messages(self, session: aiohttp.ClientSession, account: MailAccountLike) -> list[dict[str, Any]]:
            return self.responses.pop(0)

    account = MailAccount(email="user@outlook.com", mail_client_id="client", mail_refresh_token="M.C123")
    provider = StubGraphProvider()

    async def run() -> str | None:
        await provider.prime_inbox(account=account)
        return await provider.get_code(account=account, timeout=1)

    assert asyncio.run(run()) == "333333"
