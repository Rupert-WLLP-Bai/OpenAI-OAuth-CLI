from __future__ import annotations

import asyncio
from pathlib import Path
from typing import cast

import pytest

from openai_oauth_cli.accounts_db import AccountStore
import openai_oauth_cli.inbox_service as inbox_service


def _create_store_with_account(tmp_path: Path) -> AccountStore:
    db_path = tmp_path / "accounts.sqlite3"
    txt_path = tmp_path / "accounts.txt"
    txt_path.write_text(
        "user@example.com----pw----uuid-user----rt-user----x----group-a\n",
        encoding="utf-8",
    )
    store = AccountStore(db_path)
    store.init_db()
    store.import_txt_file(txt_path)
    return store


def test_fetch_inbox_reads_account_from_sqlite_and_normalizes_messages(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store = _create_store_with_account(tmp_path)
    captured: dict[str, object] = {}

    class StubProvider:
        def __init__(self, *, proxy: str | None = None) -> None:
            self.proxy = proxy

        async def fetch_messages(self, session: object, account: object) -> list[dict[str, str]]:
            return [
                {
                    "id": "message-1",
                    "subject": "OpenAI verification code",
                    "from_address": "noreply@openai.com",
                    "received_at": "2026-03-11T00:00:00+00:00",
                    "body_html": "<div>Your verification code is <b>123456</b><script>alert(1)</script></div>",
                    "body_preview": "ignored preview",
                }
            ]

    def fake_create_mail_provider(
        account: object,
        *,
        provider_choice: str = "auto",
        proxy: str | None = None,
    ) -> StubProvider:
        captured["provider_choice"] = provider_choice
        captured["provider_proxy"] = proxy
        return StubProvider(proxy=proxy)

    monkeypatch.setattr(inbox_service, "create_mail_provider", fake_create_mail_provider, raising=False)

    service = inbox_service.InboxService(store)
    payload = asyncio.run(service.fetch_inbox("user@example.com"))
    account = cast(dict[str, object], payload["account"])
    messages = cast(list[inbox_service.InboxMessage], payload["messages"])

    assert captured["provider_choice"] == "auto"
    assert account["email"] == "user@example.com"
    assert account["group_name"] == "group-a"
    assert messages[0]["id"] == "message-1"
    assert messages[0]["subject"] == "OpenAI verification code"
    assert messages[0]["from_address"] == "noreply@openai.com"
    assert messages[0]["body_text"] == "Your verification code is 123456"
    assert messages[0]["verification_code"] == "123456"
    assert "<script" not in messages[0]["body_text"]
    assert "body_html" not in messages[0]


def test_fetch_inbox_handles_missing_optional_message_fields(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store = _create_store_with_account(tmp_path)

    class StubProvider:
        def __init__(self, *, proxy: str | None = None) -> None:
            self.proxy = proxy

        async def fetch_messages(self, session: object, account: object) -> list[dict[str, str]]:
            return [{"id": "message-2"}]

    monkeypatch.setattr(
        inbox_service,
        "create_mail_provider",
        lambda account, *, provider_choice="auto", proxy=None: StubProvider(proxy=proxy),
        raising=False,
    )

    service = inbox_service.InboxService(store)
    payload = asyncio.run(service.fetch_inbox("user@example.com"))

    assert payload["messages"] == [
        {
            "id": "message-2",
            "subject": "",
            "from_address": "",
            "received_at": "",
            "body_preview": "",
            "body_text": "",
            "verification_code": None,
        }
    ]


def test_fetch_inbox_wraps_wyx66_errors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store = _create_store_with_account(tmp_path)

    class StubProvider:
        def __init__(self, *, proxy: str | None = None) -> None:
            self.proxy = proxy

        async def fetch_messages(self, session: object, account: object) -> list[dict[str, str]]:
            raise RuntimeError("wyx66 request failed with status 500")

    monkeypatch.setattr(
        inbox_service,
        "create_mail_provider",
        lambda account, *, provider_choice="auto", proxy=None: StubProvider(proxy=proxy),
        raising=False,
    )

    service = inbox_service.InboxService(store)

    with pytest.raises(RuntimeError, match="failed to fetch inbox for user@example.com"):
        asyncio.run(service.fetch_inbox("user@example.com"))
