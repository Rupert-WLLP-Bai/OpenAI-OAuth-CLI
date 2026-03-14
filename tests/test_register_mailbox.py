from __future__ import annotations

import asyncio
from typing import Any

import aiohttp
import pytest

from openai_auth_core.mailbox import MailAccountLike
from openai_register.models import MailAccountRecord
from openai_register import mailbox as register_mailbox


def test_register_provider_ignores_codes_that_existed_before_prime() -> None:
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

    class StubProvider(register_mailbox.Wyx66Provider):
        def __init__(self) -> None:
            super().__init__(api_base="https://example.invalid")
            self.responses = [[old_message], [old_message, new_message]]

        async def fetch_messages(self, session: aiohttp.ClientSession, account: MailAccountLike) -> list[dict[str, Any]]:
            return self.responses.pop(0)

    account = MailAccountRecord(email="user@example.com", mail_client_id="client", mail_refresh_token="token")
    provider = StubProvider()

    async def run() -> str | None:
        await provider.prime_inbox(account=account)
        return await provider.get_code(account=account, timeout=1)

    assert asyncio.run(run()) == "222222"


def test_register_provider_does_not_sleep_past_remaining_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    sleep_calls: list[float] = []

    class StubProvider(register_mailbox.Wyx66Provider):
        async def fetch_messages(self, session: aiohttp.ClientSession, account: MailAccountLike) -> list[dict[str, Any]]:
            return []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr("openai_auth_core.mailbox.asyncio.sleep", fake_sleep)

    account = MailAccountRecord(email="user@example.com", mail_client_id="client", mail_refresh_token="token")
    provider = StubProvider(api_base="https://example.invalid")

    async def run() -> str | None:
        loop = asyncio.get_running_loop()
        times = iter([100.0, 100.1, 100.9, 101.2])
        last = 101.2

        def fake_time() -> float:
            nonlocal last
            try:
                last = next(times)
            except StopIteration:
                pass
            return last

        monkeypatch.setattr(loop, "time", fake_time)
        return await provider.get_code(account=account, timeout=1)

    result = asyncio.run(run())

    assert result is None
    assert sleep_calls
    assert sleep_calls[0] <= 1.0
