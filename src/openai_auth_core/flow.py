from __future__ import annotations

import asyncio
import math
from collections.abc import Awaitable, Callable
from typing import Any, Protocol, cast


class FlowDeadline:
    def __init__(self, *, timeout: int, now: Callable[[], float] | None = None) -> None:
        self._now = now or (lambda: asyncio.get_running_loop().time())
        self._deadline = self._now() + timeout

    def expired(self) -> bool:
        return self._now() >= self._deadline

    def remaining_seconds(self) -> float:
        return max(0.0, self._deadline - self._now())

    def remaining_timeout(self) -> int:
        return max(0, math.ceil(self.remaining_seconds()))


class OAuthLoginDriver(Protocol):
    async def current_oauth_state(self, *, callback_url: str, callback_done: bool) -> str: ...
    async def submit_email(self, email: str) -> None: ...
    async def submit_password(self, password: str) -> None: ...
    async def submit_verification_code(self, code: str) -> None: ...
    async def click_continue(self) -> None: ...
    async def capture_debug_artifacts(self, label: str) -> None: ...
    def get_oauth_error_message(self) -> str: ...


class VerificationCodeProvider(Protocol):
    async def get_code(self, *, account: object, timeout: int) -> str | None: ...


WAIT_FOR_TRANSITION_DELAY_SECONDS = 0.1


async def run_oauth_login_flow(
    *,
    browser: OAuthLoginDriver,
    code_provider: object,
    account: object,
    email: str,
    password: str,
    timeout: int,
    callback_url: str,
    callback_done: Callable[[], bool],
    on_state_change: Callable[[str], None] | None = None,
    on_error: Callable[[], Awaitable[None]] | None = None,
) -> str:
    deadline = FlowDeadline(timeout=timeout)
    last_state = ""
    handled_once = False
    provider = cast(VerificationCodeProvider, code_provider)

    while not deadline.expired():
        state = await _get_oauth_state(
            browser,
            callback_url=callback_url,
            callback_done=callback_done(),
        )
        if state != last_state:
            last_state = state
            handled_once = False
            if on_state_change is not None:
                on_state_change(state)

        if state == "email":
            if not handled_once:
                await browser.submit_email(email)
                handled_once = True
            else:
                await asyncio.sleep(WAIT_FOR_TRANSITION_DELAY_SECONDS)
            continue
        if state == "password":
            if not handled_once:
                await browser.submit_password(password)
                handled_once = True
            else:
                await asyncio.sleep(WAIT_FOR_TRANSITION_DELAY_SECONDS)
            continue
        if state == "verification_code":
            if not handled_once:
                code = await provider.get_code(account=account, timeout=deadline.remaining_timeout())
                if not code:
                    raise RuntimeError("verification code required but unavailable")
                await browser.submit_verification_code(code)
                handled_once = True
            else:
                await asyncio.sleep(WAIT_FOR_TRANSITION_DELAY_SECONDS)
            continue
        if state == "consent":
            if not handled_once:
                await browser.click_continue()
                handled_once = True
            else:
                await asyncio.sleep(WAIT_FOR_TRANSITION_DELAY_SECONDS)
            continue
        if state == "callback":
            return state
        if state == "error":
            if on_error is not None:
                await on_error()
            raise RuntimeError(_get_oauth_error_message(browser))
        await asyncio.sleep(1)

    raise RuntimeError("login timed out before reaching callback state")


async def _get_oauth_state(browser: Any, *, callback_url: str, callback_done: bool) -> str:
    current_oauth_state = getattr(browser, "current_oauth_state", None)
    if callable(current_oauth_state):
        return await current_oauth_state(
            callback_url=callback_url,
            callback_done=callback_done,
        )

    current_state = getattr(browser, "current_state", None)
    if callable(current_state):
        return await current_state()

    raise RuntimeError("oauth login browser does not expose a state reader")


def _get_oauth_error_message(browser: Any) -> str:
    get_error_message = getattr(browser, "get_oauth_error_message", None)
    if callable(get_error_message):
        return str(get_error_message())
    return "login entered error state"
