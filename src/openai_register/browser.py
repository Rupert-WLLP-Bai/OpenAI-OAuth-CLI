from __future__ import annotations

import asyncio
from datetime import date
from typing import Any, TYPE_CHECKING, cast

from openai_auth_core.browser_actions import (
    click_first_continue_button,
    open_authorization_page as open_shared_authorization_page,
    submit_email_input,
    submit_password_input,
    submit_verification_code_input,
)
from openai_auth_core.browser_base import start_browser_session, stop_browser_session
from openai_auth_core.humanize import human_click_locator, human_type_locator
from .diagnostics import RunLogger
from .models import OAuthLoginState, RegistrationState
from .pages import (
    classify_oauth_login_state,
    classify_registration_state,
    extract_oauth_page_signals,
    extract_registration_page_signals,
    summarize_oauth_error,
)

if TYPE_CHECKING:
    from patchright.async_api import Page


PAGE_LOAD_TIMEOUT_MS = 60_000
CHATGPT_URL = "https://chatgpt.com/"


def detect_oauth_response_error(*, url: str, status: int, method: str) -> str | None:
    normalized_url = url.casefold()
    normalized_method = method.upper()

    if (
        normalized_method == "POST"
        and "/api/accounts/password/verify" in normalized_url
        and status == 401
    ):
        return "openai auth error page: incorrect email address or password"
    return None


class PatchrightBrowser:
    def __init__(self, *, proxy: str | None, logger: RunLogger | None = None) -> None:
        self.proxy = proxy
        self.logger = logger
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self._last_oauth_signals = None
        self._oauth_response_error_message: str | None = None

    async def __aenter__(self) -> PatchrightBrowser:
        self.playwright, self.browser, self.context, self.page = await start_browser_session(proxy=self.proxy)
        self.page.on("response", lambda response: asyncio.create_task(self._handle_response(response)))
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        await stop_browser_session(playwright=self.playwright, browser=self.browser, context=self.context)

    async def open_chatgpt(self) -> None:
        assert self.page is not None
        await self.page.goto(CHATGPT_URL, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_MS)
        await asyncio.sleep(2)
        self._log_event("navigation", flow="register", url=self.page.url)

    async def open_authorization_page(self, auth_url: str) -> None:
        assert self.page is not None
        await open_shared_authorization_page(self.page, auth_url, timeout_ms=PAGE_LOAD_TIMEOUT_MS)
        self._log_event("navigation", flow="verify-login", url=self.page.url)

    async def current_state(self) -> RegistrationState:
        assert self.page is not None
        signals = await extract_registration_page_signals(self.page)
        state = classify_registration_state(signals)
        self._log_event("page_state", flow="register", state=state, signals=signals)
        return state

    async def current_oauth_state(self, *, callback_url: str, callback_done: bool) -> OAuthLoginState:
        assert self.page is not None
        if self._oauth_response_error_message:
            self._log_event(
                "network_error_state",
                flow="verify-login",
                error=self._oauth_response_error_message,
            )
            return "error"
        signals = await extract_oauth_page_signals(self.page)
        self._last_oauth_signals = signals
        state = classify_oauth_login_state(signals, callback_url=callback_url, callback_done=callback_done)
        self._log_event("page_state", flow="verify-login", state=state, signals=signals)
        return cast(OAuthLoginState, state)

    async def click_signup(self) -> None:
        assert self.page is not None
        self._log_event("action", flow="register", action="click_signup")
        selectors = (
            '[data-testid="signup-button"]',
            'button:has-text("免费注册")',
            'button:has-text("Sign up")',
            'button:has-text("注册")',
        )
        await self._click_first(selectors, "failed to locate a signup button")

    async def submit_email(self, email: str) -> None:
        assert self.page is not None
        self._log_event("action", flow="auth", action="submit_email", email=email)
        await submit_email_input(self.page, email, continue_cb=self._click_continue)

    async def submit_password(self, password: str) -> None:
        assert self.page is not None
        self._log_event("action", flow="auth", action="submit_password", password="<redacted>")
        await submit_password_input(self.page, password, continue_cb=self._click_continue)

    async def submit_verification_code(self, code: str) -> None:
        assert self.page is not None
        self._log_event("action", flow="auth", action="submit_verification_code", code="<redacted>")
        await submit_verification_code_input(self.page, code, continue_cb=self._click_continue)

    async def submit_profile(self, full_name: str, birthday: date) -> None:
        assert self.page is not None
        self._log_event("action", flow="register", action="submit_profile", full_name=full_name, birthday=birthday)
        name_input = await self.page.wait_for_selector(
            'input[autocomplete="name"], input[name="name"], input[placeholder*="全名" i]',
            timeout=10_000,
        )
        if name_input is None:
            raise RuntimeError("failed to locate the full name input")
        await human_type_locator(page=self.page, locator=name_input, text=full_name)
        await asyncio.sleep(0.5)
        await self._fill_birthday(self.page, birthday)
        await asyncio.sleep(0.5)
        await self._click_continue()

    async def click_continue(self) -> None:
        self._log_event("action", flow="auth", action="click_continue")
        await self._click_continue()

    async def capture_debug_artifacts(self, label: str) -> None:
        if self.page is None or self.logger is None:
            return
        await self.logger.capture_page(self.page, label=label)

    def get_oauth_error_message(self) -> str:
        if self._oauth_response_error_message:
            return self._oauth_response_error_message
        if self._last_oauth_signals is None:
            return "login entered error state"
        return summarize_oauth_error(self._last_oauth_signals)

    async def _fill_birthday(self, page: Page, birthday: date) -> None:
        segments = (
            ('[data-type="year"][role="spinbutton"]', f"{birthday.year:04d}"),
            ('[data-type="month"][role="spinbutton"]', f"{birthday.month:02d}"),
            ('[data-type="day"][role="spinbutton"]', f"{birthday.day:02d}"),
        )
        for selector, value in segments:
            segment = page.locator(selector).first
            await human_click_locator(page=page, locator=segment)
            await page.keyboard.press("Control+A")
            await page.keyboard.type(value, delay=90)

    async def _click_continue(self) -> None:
        assert self.page is not None
        await click_first_continue_button(self.page)

    async def _click_first(self, selectors: tuple[str, ...], error_message: str) -> None:
        assert self.page is not None
        for selector in selectors:
            try:
                locator = self.page.locator(selector).first
                if await locator.count() == 0:
                    continue
                await human_click_locator(page=self.page, locator=locator)
                await asyncio.sleep(2)
                return
            except Exception:
                continue
        raise RuntimeError(error_message)

    def _log_event(self, event: str, **fields: Any) -> None:
        if self.logger is not None:
            self.logger.log_event(event, **fields)

    async def _handle_response(self, response: Any) -> None:
        try:
            error_message = detect_oauth_response_error(
                url=response.url,
                status=int(response.status),
                method=response.request.method,
            )
        except Exception:
            return

        if error_message:
            self._oauth_response_error_message = error_message
            self._log_event(
                "network_response_error",
                flow="verify-login",
                url=response.url,
                status=int(response.status),
                method=response.request.method,
                error=error_message,
            )
