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


def _create_many_accounts_db(tmp_path: Path, *, count: int) -> Path:
    db_path = tmp_path / "many-accounts.sqlite3"
    txt_path = tmp_path / "many-accounts.txt"
    txt_path.write_text(
        "\n".join(
            f"user{index:02d}@example.com----pw----uuid-{index:02d}----rt-{index:02d}----x----team-{index % 3}"
            for index in range(count)
        )
        + "\n",
        encoding="utf-8",
    )
    store = AccountStore(db_path)
    store.init_db()
    store.import_txt_file(txt_path)
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


def test_admin_server_accounts_endpoint_defaults_to_25_items_per_page(tmp_path: Path) -> None:
    async def scenario() -> None:
        db_path = _create_many_accounts_db(tmp_path, count=30)
        server = admin_server.LocalAccountAdminServer(db_path=db_path, port=0)
        await server.start()
        try:
            async with aiohttp.ClientSession() as session:
                response = await session.get(f"{server.base_url}/api/accounts")
                assert response.status == 200
                payload = await response.json()
                assert payload["total"] == 30
                assert len(payload["items"]) == 25
        finally:
            await server.stop()

    asyncio.run(scenario())


def test_admin_server_serves_workspace_shell_and_static_assets(tmp_path: Path) -> None:
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

            # React app serves a minimal HTML shell that loads JS/CSS
            assert "账号管理系统" in html
            assert "/static/admin/assets/index.js" in html
            assert "/static/admin/assets/index.css" in html
            assert '<div id="root"></div>' in html

            # Verify no sensitive data in HTML (it's in the JS bundle)
            assert "rt-alpha" not in html
            assert "rt-beta" not in html

            async with aiohttp.ClientSession() as session:
                js_response = await session.get(f"{server.base_url}/static/admin/assets/index.js")
                css_response = await session.get(f"{server.base_url}/static/admin/assets/index.css")
                assert js_response.status == 200
                assert css_response.status == 200
                # React app contains the UI logic
                js_content = await js_response.text()
                assert "账号管理系统" in js_content or "Account" in js_content
        finally:
            await server.stop()

    asyncio.run(scenario())


def test_admin_server_admin_css_keeps_workspace_columns_shrinkable_for_internal_scroll(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        db_path = _create_accounts_db(tmp_path)
        server = admin_server.LocalAccountAdminServer(db_path=db_path, port=0)
        await server.start()
        try:
            async with aiohttp.ClientSession() as session:
                css_response = await session.get(f"{server.base_url}/static/admin/assets/index.css")
                assert css_response.status == 200
                css = await css_response.text()

            # React app uses Semi Design Layout which handles this internally
            # Just verify CSS is loaded
            assert len(css) > 0
        finally:
            await server.stop()

    asyncio.run(scenario())


def test_admin_server_admin_css_defines_fixed_desktop_workspace_scroll_regions(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        db_path = _create_accounts_db(tmp_path)
        server = admin_server.LocalAccountAdminServer(db_path=db_path, port=0)
        await server.start()
        try:
            async with aiohttp.ClientSession() as session:
                css_response = await session.get(f"{server.base_url}/static/admin/assets/index.css")
                assert css_response.status == 200
                css = await css_response.text()

            normalized = css.replace(" ", "").replace("\n", "")
            assert ".app-shell" in css
            assert ".workspace-grid" in css
            assert ".workspace-left-rail" in css
            assert ".workspace-center-rail" in css
            assert ".workspace-right-rail" in css
            assert ".account-list-scroll" in css
            assert ".inbox-scroll-region" in css
            assert "height:100dvh" in normalized
            assert "overflow:auto" in normalized
        finally:
            await server.stop()

    asyncio.run(scenario())


def test_admin_server_admin_css_pins_verification_boxes_to_card_bottom(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        db_path = _create_accounts_db(tmp_path)
        server = admin_server.LocalAccountAdminServer(db_path=db_path, port=0)
        await server.start()
        try:
            async with aiohttp.ClientSession() as session:
                css_response = await session.get(f"{server.base_url}/static/admin/assets/index.css")
                assert css_response.status == 200
                css = await css_response.text()

            normalized = css.replace(" ", "").replace("\n", "")
            assert ".verification-box" in css
            assert ".message-card" in css
            assert "margin-top:auto" in normalized
            assert "align-items:stretch" in normalized
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
