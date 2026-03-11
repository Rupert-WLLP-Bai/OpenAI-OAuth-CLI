from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from openai_auth_core.browser_base import start_browser_session, stop_browser_session
from openai_auth_core.humanize import human_click_locator, human_type_locator
from .pages import classify_auth_page_state, extract_auth_page_signals

if TYPE_CHECKING:
    from openai_oauth_cli.callback import CallbackResult


PAGE_LOAD_TIMEOUT_MS = 60_000


class PatchrightBrowser:
    def __init__(
        self,
        *,
        proxy: str | None,
        callback_port: int,
        callback_task: asyncio.Task[CallbackResult],
    ) -> None:
        self.proxy = proxy
        self.callback_port = callback_port
        self.callback_task = callback_task
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    async def __aenter__(self) -> PatchrightBrowser:
        self.playwright, self.browser, self.context, self.page = await start_browser_session(proxy=self.proxy)
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        await stop_browser_session(playwright=self.playwright, browser=self.browser, context=self.context)

    async def open_authorization_page(self, auth_url: str) -> None:
        assert self.page is not None
        await self.page.goto(auth_url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_MS)
        await asyncio.sleep(2)

    async def current_state(self) -> str:
        if self.callback_task.done():
            return "callback"
        assert self.page is not None
        signals = await extract_auth_page_signals(self.page)
        return classify_auth_page_state(signals, callback_port=self.callback_port)

    async def submit_email(self, email: str) -> None:
        assert self.page is not None
        email_input = await self.page.wait_for_selector(
            'input[type="email"], input[name="username"]:not([type="hidden"]), input[placeholder*="email" i]',
            timeout=10_000,
        )
        if email_input is None:
            raise RuntimeError("failed to locate the email input")
        await human_type_locator(page=self.page, locator=email_input, text=email)
        await asyncio.sleep(0.5)
        await self.click_continue()

    async def submit_password(self, password: str) -> None:
        assert self.page is not None
        password_input = await self.page.wait_for_selector(
            'input[type="password"], input[name="password"]',
            timeout=10_000,
        )
        if password_input is None:
            raise RuntimeError("failed to locate the password input")
        await human_type_locator(page=self.page, locator=password_input, text=password)
        await asyncio.sleep(0.5)
        await self.click_continue()

    async def submit_verification_code(self, code: str) -> None:
        assert self.page is not None
        verification_input = await self.page.wait_for_selector(
            'input[placeholder*="code" i], input[name*="code" i], input[type="text"][autocomplete="one-time-code"]',
            timeout=10_000,
        )
        if verification_input is None:
            raise RuntimeError("failed to locate the verification code input")
        await human_type_locator(page=self.page, locator=verification_input, text=code)
        await asyncio.sleep(0.5)
        await self.click_continue()

    async def click_continue(self) -> None:
        assert self.page is not None
        selectors = (
            'button[type="submit"]',
            'button:text-is("Continue")',
            'button:text-is("Next")',
            'button:text-is("Allow")',
            'button:text-is("Confirm")',
            'button:text-is("继续")',
            'button:text-is("确认")',
        )
        for selector in selectors:
            try:
                button = await self.page.query_selector(selector)
                if button is None:
                    continue
                await human_click_locator(page=self.page, locator=button)
                await asyncio.sleep(2)
                return
            except Exception:
                continue
        raise RuntimeError("failed to locate a continue button")
