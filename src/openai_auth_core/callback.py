from __future__ import annotations

import asyncio
from dataclasses import dataclass

from aiohttp import web


@dataclass(frozen=True)
class CallbackResult:
    code: str = ""
    state: str = ""
    error: str = ""
    error_description: str = ""


class CallbackServer:
    def __init__(self, *, port: int) -> None:
        self._requested_port = port
        self._callback_url = ""
        self._app = web.Application()
        self._app.router.add_get("/auth/callback", self._handle_callback)
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._result_future: asyncio.Future[CallbackResult] | None = None

    @property
    def callback_url(self) -> str:
        if not self._callback_url:
            raise RuntimeError("callback server has not been started")
        return self._callback_url

    async def start(self) -> None:
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, host="127.0.0.1", port=self._requested_port)
        self._result_future = asyncio.get_running_loop().create_future()
        await self._site.start()

        assert self._runner is not None
        addresses = self._runner.addresses
        if not addresses:
            raise RuntimeError("callback server did not expose a listening address")

        address = addresses[0]
        self._callback_url = f"http://localhost:{int(address[1])}/auth/callback"

    async def stop(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()
        self._runner = None
        self._site = None

    async def wait_for_result(self, *, timeout: float) -> CallbackResult:
        if self._result_future is None:
            raise RuntimeError("callback server has not been started")
        return await asyncio.wait_for(self._result_future, timeout)

    async def _handle_callback(self, request: web.Request) -> web.Response:
        if self._result_future is None:
            raise web.HTTPInternalServerError(text="callback server is not ready")

        result = CallbackResult(
            code=request.query.get("code", ""),
            state=request.query.get("state", ""),
            error=request.query.get("error", ""),
            error_description=request.query.get("error_description", ""),
        )
        if not self._result_future.done():
            self._result_future.set_result(result)

        if result.error:
            raise web.HTTPBadRequest(text=f"OAuth error: {result.error}")

        return web.Response(text="Authentication received. You can close this window.")
