from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, cast

from aiohttp import web

from .accounts_db import AccountStore, ImportTextSource
from .admin_views import render_admin_shell
from .inbox_service import InboxService


class LocalAccountAdminServer:
    def __init__(
        self,
        *,
        db_path: Path,
        port: int,
        proxy: str | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.port = port
        self.proxy = proxy
        self._base_url = ""
        self._store = AccountStore(self.db_path)
        self._app = web.Application(middlewares=[self._cache_control_middleware])
        self._app.router.add_get("/", self._handle_root)
        self._app.router.add_get("/api/summary", self._handle_summary)
        self._app.router.add_get("/api/groups", self._handle_groups)
        self._app.router.add_get("/api/accounts", self._handle_list_accounts)
        self._app.router.add_patch("/api/accounts/{account_id}", self._handle_update_account)
        self._app.router.add_post("/api/accounts/bulk-update", self._handle_bulk_update)
        self._app.router.add_post("/api/accounts/import-txt", self._handle_import_txt)
        self._app.router.add_get("/api/accounts/export", self._handle_export_accounts)
        self._app.router.add_get("/api/accounts/{account_id}/inbox", self._handle_account_inbox)
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._forever: asyncio.Future[None] | None = None

    @property
    def base_url(self) -> str:
        if not self._base_url:
            raise RuntimeError("admin server has not been started")
        return self._base_url

    @web.middleware
    async def _cache_control_middleware(
        self,
        request: web.Request,
        handler: Any,
    ) -> web.StreamResponse:
        response = await handler(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    async def start(self) -> None:
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, host="127.0.0.1", port=self.port)
        await self._site.start()

        assert self._runner is not None
        addresses = self._runner.addresses
        if not addresses:
            raise RuntimeError("admin server did not expose a listening address")

        address = addresses[0]
        self._base_url = f"http://localhost:{int(address[1])}"

    async def stop(self) -> None:
        if self._forever is not None and not self._forever.done():
            self._forever.cancel()
        if self._runner is not None:
            await self._runner.cleanup()
        self._runner = None
        self._site = None

    async def wait_until_cancelled(self) -> None:
        self._forever = asyncio.get_running_loop().create_future()
        await self._forever

    def _json(self, payload: Any, *, status: int = 200) -> web.Response:
        return web.json_response(payload, status=status)

    def _lookup_account_email(self, account_id: int) -> str:
        try:
            return self._store.get_account_email_by_id(account_id)
        except ValueError:
            raise web.HTTPNotFound(text='{"error":"account not found"}', content_type="application/json")

    async def _handle_root(self, request: web.Request) -> web.Response:
        del request
        return web.Response(text=render_admin_shell(), content_type="text/html", headers={"Cache-Control": "no-store"})

    async def _handle_summary(self, request: web.Request) -> web.Response:
        del request
        return self._json(self._store.get_summary())

    async def _handle_groups(self, request: web.Request) -> web.Response:
        del request
        summary = self._store.get_summary()
        groups_by_name = cast(dict[str, int], summary["groups"])
        groups = sorted(str(group_name) for group_name in groups_by_name.keys())
        return self._json(groups)

    async def _handle_list_accounts(self, request: web.Request) -> web.Response:
        raw_is_registered = request.query.get("is_registered")
        is_registered: bool | None = None
        if raw_is_registered is not None:
            is_registered = raw_is_registered.strip().casefold() in {"1", "true", "yes"}
        payload = self._store.list_accounts(
            query=request.query.get("query", ""),
            group_name=request.query.get("group_name") or None,
            is_registered=is_registered,
            limit=int(request.query.get("limit", "50")),
            offset=int(request.query.get("offset", "0")),
        )
        return self._json(payload)

    async def _handle_update_account(self, request: web.Request) -> web.Response:
        account_id = int(request.match_info["account_id"])
        email = self._lookup_account_email(account_id)
        body = await request.json()
        updated = self._store.update_account(
            email,
            group_name=body.get("group_name"),
            is_registered=body.get("is_registered"),
            is_primary=body.get("is_primary"),
        )
        return self._json(updated)

    async def _handle_bulk_update(self, request: web.Request) -> web.Response:
        body = await request.json()
        updated = self._store.bulk_update_accounts(
            emails=body.get("emails", []),
            group_name=body.get("group_name"),
            is_registered=body.get("is_registered"),
            is_primary=body.get("is_primary"),
        )
        return self._json({"updated": updated})

    async def _handle_import_txt(self, request: web.Request) -> web.Response:
        body = await request.json()
        sources = [
            ImportTextSource(
                source_name=str(source.get("source_name", "")),
                source_path=str(source.get("source_path", source.get("source_name", ""))),
                text=str(source.get("text", "")),
            )
            for source in body.get("sources", [])
        ]
        stats = self._store.import_text_sources(sources)
        return self._json({"imported": stats.imported, "skipped": stats.skipped})

    async def _handle_export_accounts(self, request: web.Request) -> web.Response:
        payload = self._store.export_accounts(
            format="json",
            group_name=request.query.get("group_name") or None,
        )
        return web.Response(text=payload, content_type="application/json", headers={"Cache-Control": "no-store"})

    async def _handle_account_inbox(self, request: web.Request) -> web.Response:
        account_id = int(request.match_info["account_id"])
        email = self._lookup_account_email(account_id)
        service = InboxService(self._store, proxy=self.proxy)
        payload = await service.fetch_inbox(email)
        return self._json(payload)
