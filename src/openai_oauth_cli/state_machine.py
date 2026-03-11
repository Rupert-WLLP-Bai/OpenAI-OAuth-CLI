from __future__ import annotations

import asyncio
from typing import Protocol

from openai_auth_core.flow import FlowDeadline

from .mailbox import VerificationCodeProvider
from .models import AccountRecord


class BrowserDriver(Protocol):
    async def open_authorization_page(self, auth_url: str) -> None: ...
    async def current_state(self) -> str: ...
    async def submit_email(self, email: str) -> None: ...
    async def submit_password(self, password: str) -> None: ...
    async def submit_verification_code(self, code: str) -> None: ...
    async def click_continue(self) -> None: ...


WAIT_FOR_TRANSITION_DELAY_SECONDS = 0.1


class LoginStateMachine:
    def __init__(self, *, browser: BrowserDriver, code_provider: VerificationCodeProvider) -> None:
        self.browser = browser
        self.code_provider = code_provider

    async def complete_login(self, *, account: AccountRecord, email: str, password: str, timeout: int) -> str:
        deadline = FlowDeadline(timeout=timeout)
        last_state = ""
        handled_once = False

        while not deadline.expired():
            state = await self.browser.current_state()
            if state != last_state:
                last_state = state
                handled_once = False

            if state == "email":
                if not handled_once:
                    await self.browser.submit_email(email)
                    handled_once = True
                else:
                    await asyncio.sleep(WAIT_FOR_TRANSITION_DELAY_SECONDS)
                continue
            if state == "password":
                if not handled_once:
                    await self.browser.submit_password(password)
                    handled_once = True
                else:
                    await asyncio.sleep(WAIT_FOR_TRANSITION_DELAY_SECONDS)
                continue
            if state == "verification_code":
                if not handled_once:
                    remaining_timeout = deadline.remaining_timeout()
                    code = await self.code_provider.get_code(account=account, timeout=remaining_timeout)
                    if not code:
                        raise RuntimeError("verification code required but unavailable")
                    await self.browser.submit_verification_code(code)
                    handled_once = True
                else:
                    await asyncio.sleep(WAIT_FOR_TRANSITION_DELAY_SECONDS)
                continue
            if state == "consent":
                if not handled_once:
                    await self.browser.click_continue()
                    handled_once = True
                else:
                    await asyncio.sleep(WAIT_FOR_TRANSITION_DELAY_SECONDS)
                continue
            if state == "callback":
                return state
            if state == "error":
                raise RuntimeError("login entered error state")
            await asyncio.sleep(1)

        raise RuntimeError("login timed out before reaching callback state")
