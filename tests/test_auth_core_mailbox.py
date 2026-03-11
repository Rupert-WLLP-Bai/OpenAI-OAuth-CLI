from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import aiohttp

from openai_auth_core.mailbox import MailAccountLike, Wyx66Provider


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

        async def fetch_messages(
            self,
            session: aiohttp.ClientSession,
            account: MailAccountLike,
        ) -> list[dict[str, Any]]:
            return self.responses.pop(0)

    account = MailAccount(email="user@example.com", mail_client_id="client", mail_refresh_token="token")
    provider = StubProvider()

    async def run() -> str | None:
        await provider.prime_inbox(account=account)
        return await provider.get_code(account=account, timeout=1)

    assert asyncio.run(run()) == "222222"
