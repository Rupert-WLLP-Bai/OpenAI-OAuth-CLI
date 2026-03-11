from __future__ import annotations

import asyncio

import aiohttp

from openai_auth_core.callback import CallbackServer


def test_auth_core_callback_server_captures_code_and_state() -> None:
    async def scenario() -> None:
        server = CallbackServer(port=0)
        await server.start()
        try:
            callback_url = server.callback_url + "?code=abc123&state=expected"
            async with aiohttp.ClientSession() as session:
                async with session.get(callback_url) as response:
                    assert response.status == 200
            result = await server.wait_for_result(timeout=1)
            assert result.code == "abc123"
            assert result.state == "expected"
        finally:
            await server.stop()

    asyncio.run(scenario())


def test_auth_core_callback_server_captures_oauth_error() -> None:
    async def scenario() -> None:
        server = CallbackServer(port=0)
        await server.start()
        try:
            callback_url = server.callback_url + "?error=access_denied&state=expected"
            async with aiohttp.ClientSession() as session:
                async with session.get(callback_url) as response:
                    assert response.status == 400
            result = await server.wait_for_result(timeout=1)
            assert result.error == "access_denied"
        finally:
            await server.stop()

    asyncio.run(scenario())
