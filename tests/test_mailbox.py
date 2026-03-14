from __future__ import annotations

import asyncio
from typing import Any

import aiohttp
import pytest

from openai_auth_core.mailbox import MailAccountLike
from openai_oauth_cli.models import AccountRecord
from openai_oauth_cli.mailbox import find_account_by_email, parse_accounts_text
from openai_oauth_cli import mailbox as oauth_mailbox


def test_parse_accounts_text_extracts_client_metadata() -> None:
    accounts = parse_accounts_text("a@example.com----pw----uuid-1----mail-rt----x----group\n")

    assert len(accounts) == 1
    assert accounts[0].email == "a@example.com"
    assert accounts[0].mail_client_id == "uuid-1"
    assert accounts[0].mail_refresh_token == "mail-rt"


def test_parse_accounts_text_preserves_refresh_token_suffixes() -> None:
    accounts = parse_accounts_text("a@example.com----pw----uuid-1----mail-rt$$----x----default\n")

    assert len(accounts) == 1
    assert accounts[0].mail_refresh_token == "mail-rt$$"


def test_find_account_by_email_requires_unique_match() -> None:
    accounts = parse_accounts_text(
        "a@example.com----pw----uuid-1----mail-rt-1----x----group\n"
        "a@example.com----pw----uuid-2----mail-rt-2----x----group\n"
    )

    try:
        find_account_by_email(accounts, "a@example.com")
    except ValueError as exc:
        assert "multiple accounts" in str(exc)
    else:
        raise AssertionError("expected duplicate account lookup to fail")

def test_wyx66_provider_ignores_codes_that_existed_before_prime() -> None:
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

    class StubProvider(oauth_mailbox.Wyx66Provider):
        def __init__(self) -> None:
            super().__init__(api_base="https://example.invalid")
            self.responses = [[old_message], [old_message, new_message]]

        async def fetch_messages(self, session: aiohttp.ClientSession, account: MailAccountLike) -> list[dict[str, Any]]:
            return self.responses.pop(0)

    account = AccountRecord(email="user@example.com", mail_client_id="client", mail_refresh_token="token")
    provider = StubProvider()

    async def run() -> str | None:
        await provider.prime_inbox(account=account)
        return await provider.get_code(account=account, timeout=1)

    assert asyncio.run(run()) == "222222"


def test_wyx66_provider_does_not_sleep_past_remaining_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    sleep_calls: list[float] = []

    class StubProvider(oauth_mailbox.Wyx66Provider):
        async def fetch_messages(self, session: aiohttp.ClientSession, account: MailAccountLike) -> list[dict[str, Any]]:
            return []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr("openai_auth_core.mailbox.asyncio.sleep", fake_sleep)

    account = AccountRecord(email="user@example.com", mail_client_id="client", mail_refresh_token="token")
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
