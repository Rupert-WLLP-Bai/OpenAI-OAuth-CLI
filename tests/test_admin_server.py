from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from typing import Any

import aiohttp

from openai_oauth_cli.accounts_db import AccountStore
import openai_oauth_cli.admin_server as admin_server


def _create_accounts_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "accounts.sqlite3"
    txt_path = tmp_path / "accounts.txt"
    txt_path.write_text(
        "\n".join(
            [
                "alpha@example.com----pw----uuid-alpha----rt-alpha----x----group-a",
                "beta@example.com----pw----uuid-beta----rt-beta----x----group-b",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    store = AccountStore(db_path)
    store.init_db()
    store.import_txt_file(txt_path)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "UPDATE accounts SET is_registered = 1, is_primary = 1 WHERE lower(email) = lower(?)",
            ("beta@example.com",),
        )
        connection.commit()
    return db_path


def test_admin_server_allows_direct_api_access_without_bootstrap(tmp_path: Path) -> None:
    async def scenario() -> None:
        db_path = _create_accounts_db(tmp_path)
        server = admin_server.LocalAccountAdminServer(db_path=db_path, port=0)
        await server.start()
        try:
            async with aiohttp.ClientSession() as session:
                response = await session.get(f"{server.base_url}/api/summary")
                assert response.status == 200
                assert response.headers["Cache-Control"] == "no-store"
                payload = await response.json()
                assert payload["accounts"] == 2
                assert payload["registered"] == 1
        finally:
            await server.stop()

    asyncio.run(scenario())


def test_admin_server_serves_minimal_admin_shell(tmp_path: Path) -> None:
    async def scenario() -> None:
        db_path = _create_accounts_db(tmp_path)
        server = admin_server.LocalAccountAdminServer(db_path=db_path, port=0)
        await server.start()
        try:
            async with aiohttp.ClientSession() as session:
                response = await session.get(f"{server.base_url}/")
                assert response.status == 200
                assert response.headers["Cache-Control"] == "no-store"
                html = await response.text()

            assert "账号管理系统" in html
            assert "account-search" in html
            assert "group-filter" in html
            assert "status-filter" in html
            assert "import-button" in html
            assert "export-button" in html
            assert "batch-group-input" in html
            assert "apply-batch-button" in html
            assert "import-textarea" in html
            assert "account-detail-panel" in html
            assert "inbox-panel" in html
            assert "inbox-loading-indicator" in html
            assert "加载邮件中" in html
            assert "loadAccounts" in html
            assert "applyBulkUpdate" in html
            assert "fetchInbox" in html
            assert "refreshSelectedAccountDetail" in html
            assert "extractCode(" not in html
            assert "mail_refresh_token" not in html
            assert "rt-alpha" not in html
            assert "rt-beta" not in html
        finally:
            await server.stop()

    asyncio.run(scenario())


def test_admin_server_routes_cover_summary_groups_accounts_and_updates(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        db_path = _create_accounts_db(tmp_path)
        server = admin_server.LocalAccountAdminServer(db_path=db_path, port=0)
        await server.start()
        try:
            async with aiohttp.ClientSession() as session:
                summary_response = await session.get(f"{server.base_url}/api/summary")
                groups_response = await session.get(f"{server.base_url}/api/groups")
                accounts_response = await session.get(
                    f"{server.base_url}/api/accounts",
                    params={"query": "beta", "group_name": "group-b", "is_registered": "true"},
                )

                assert summary_response.status == 200
                assert groups_response.status == 200
                assert accounts_response.status == 200

                summary = await summary_response.json()
                groups = await groups_response.json()
                accounts = await accounts_response.json()

                assert summary["groups"] == {"group-a": 1, "group-b": 1}
                assert groups == ["group-a", "group-b"]
                assert accounts["total"] == 1
                assert accounts["items"][0]["email"] == "beta@example.com"

                account_id = int(accounts["items"][0]["id"])

                patch_response = await session.patch(
                    f"{server.base_url}/api/accounts/{account_id}",
                    json={"group_name": "ops", "is_primary": True},
                )
                assert patch_response.status == 200
                updated = await patch_response.json()
                assert updated["group_name"] == "ops"
                assert updated["is_registered"] is True
                assert updated["is_primary"] is True

                bulk_response = await session.post(
                    f"{server.base_url}/api/accounts/bulk-update",
                    json={"emails": ["alpha@example.com"], "group_name": "batch", "is_registered": True},
                )
                assert bulk_response.status == 200
                bulk_payload = await bulk_response.json()
                assert bulk_payload == {"updated": 1}

                import_response = await session.post(
                    f"{server.base_url}/api/accounts/import-txt",
                    json={
                        "sources": [
                            {
                                "source_name": "upload-1.txt",
                                "source_path": "upload://upload-1.txt",
                                "text": "upload@example.com----pw----uuid-upload----rt-upload----x----uploads\n",
                            }
                        ]
                    },
                )
                assert import_response.status == 200
                import_payload = await import_response.json()
                assert import_payload == {"imported": 1, "skipped": 0}

                export_response = await session.get(
                    f"{server.base_url}/api/accounts/export",
                    params={"group_name": "ops"},
                )
                assert export_response.status == 200
                exported = await export_response.json()
                assert [row["email"] for row in exported] == ["beta@example.com"]
        finally:
            await server.stop()

    asyncio.run(scenario())


def test_admin_server_returns_account_inbox(tmp_path: Path, monkeypatch) -> None:
    async def scenario() -> None:
        db_path = _create_accounts_db(tmp_path)

        class StubInboxService:
            def __init__(self, store: Any, *, proxy: str | None = None) -> None:
                self.store = store
                self.proxy = proxy

            async def fetch_inbox(self, email: str) -> dict[str, object]:
                return {
                    "account": {"email": email, "group_name": "group-b", "is_registered": True, "is_primary": True},
                    "messages": [{"id": "message-1", "subject": "Hello", "from_address": "noreply@openai.com", "received_at": "", "body_preview": "", "body_text": "Hello", "verification_code": "654321"}],
                }

        monkeypatch.setattr(admin_server, "InboxService", StubInboxService)

        server = admin_server.LocalAccountAdminServer(db_path=db_path, port=0)
        await server.start()
        try:
            async with aiohttp.ClientSession() as session:
                accounts_response = await session.get(f"{server.base_url}/api/accounts", params={"query": "beta"})
                accounts = await accounts_response.json()
                account_id = int(accounts["items"][0]["id"])

                inbox_response = await session.get(f"{server.base_url}/api/accounts/{account_id}/inbox")
                assert inbox_response.status == 200
                payload = await inbox_response.json()
                assert payload["account"]["email"] == "beta@example.com"
                assert payload["messages"][0]["subject"] == "Hello"
                assert payload["messages"][0]["verification_code"] == "654321"
        finally:
            await server.stop()

    asyncio.run(scenario())


def test_admin_server_uses_store_email_lookup_for_account_routes(tmp_path: Path, monkeypatch) -> None:
    async def scenario() -> None:
        db_path = _create_accounts_db(tmp_path)
        server = admin_server.LocalAccountAdminServer(db_path=db_path, port=0)
        await server.start()
        try:
            async with aiohttp.ClientSession() as session:
                accounts_response = await session.get(f"{server.base_url}/api/accounts", params={"query": "beta"})
                accounts = await accounts_response.json()
                account_id = int(accounts["items"][0]["id"])

                lookup_calls: list[int] = []

                def fake_get_account_email_by_id(requested_id: int) -> str:
                    lookup_calls.append(requested_id)
                    return "beta@example.com"

                monkeypatch.setattr(server._store, "get_account_email_by_id", fake_get_account_email_by_id)

                def failing_connect():
                    raise AssertionError("route should not reach into _connect for account email lookup")

                monkeypatch.setattr(server._store, "_connect", failing_connect)
                class StubInboxService:
                    def __init__(self, store: Any, *, proxy: str | None = None) -> None:
                        self.store = store
                        self.proxy = proxy

                    async def fetch_inbox(self, email: str) -> dict[str, object]:
                        return {"account": {"email": email}, "messages": []}

                monkeypatch.setattr(admin_server, "InboxService", StubInboxService)

                inbox_response = await session.get(f"{server.base_url}/api/accounts/{account_id}/inbox")
                assert inbox_response.status == 200
                assert lookup_calls == [account_id]
        finally:
            await server.stop()

    asyncio.run(scenario())
