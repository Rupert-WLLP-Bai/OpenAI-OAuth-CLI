from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from openai_auth_core.browser_actions import (
    click_first_continue_button,
    open_authorization_page as open_shared_authorization_page,
    submit_email_input,
    submit_password_input,
    submit_verification_code_input,
)
from openai_auth_core.browser_base import start_browser_session, stop_browser_session
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
        await open_shared_authorization_page(self.page, auth_url, timeout_ms=PAGE_LOAD_TIMEOUT_MS)

    async def current_state(self) -> str:
        if self.callback_task.done():
            return "callback"
        assert self.page is not None
        signals = await extract_auth_page_signals(self.page)
        return classify_auth_page_state(signals, callback_port=self.callback_port)

    async def submit_email(self, email: str) -> None:
        assert self.page is not None
        await submit_email_input(self.page, email, continue_cb=self.click_continue)

    async def submit_password(self, password: str) -> None:
        assert self.page is not None
        await submit_password_input(self.page, password, continue_cb=self.click_continue)

    async def submit_verification_code(self, code: str) -> None:
        assert self.page is not None
        await submit_verification_code_input(self.page, code, continue_cb=self.click_continue)

    async def click_continue(self) -> None:
        assert self.page is not None
        await click_first_continue_button(self.page)
