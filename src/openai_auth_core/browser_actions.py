from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from .humanize import human_click_locator, human_type_locator


PAGE_LOAD_TIMEOUT_MS = 60_000
ACTION_DELAY_SECONDS = 0.5
NAVIGATION_DELAY_SECONDS = 2.0

EMAIL_INPUT_SELECTOR = 'input[type="email"], input[name="username"]:not([type="hidden"]), input[placeholder*="email" i], input[placeholder*="电子邮件" i]'
PASSWORD_INPUT_SELECTOR = 'input[type="password"], input[name="password"]'
VERIFICATION_CODE_INPUT_SELECTOR = 'input[autocomplete="one-time-code"], input[placeholder*="验证码" i], input[placeholder*="code" i], input[name*="code" i], input[type="text"][autocomplete="one-time-code"]'
CONTINUE_BUTTON_SELECTORS = (
    'button[type="submit"]',
    'button:text-is("Continue")',
    'button:text-is("Next")',
    'button:text-is("Allow")',
    'button:text-is("Confirm")',
    'button:text-is("继续")',
    'button:text-is("确认")',
    'button:text-is("完成帐户创建")',
    'button:text-is("完成账户创建")',
)


async def open_authorization_page(page: Any, auth_url: str, *, timeout_ms: int = PAGE_LOAD_TIMEOUT_MS) -> None:
    await page.goto(auth_url, wait_until="domcontentloaded", timeout=timeout_ms)
    await asyncio.sleep(NAVIGATION_DELAY_SECONDS)


async def submit_email_input(page: Any, email: str, *, continue_cb: Callable[[], Awaitable[None]]) -> None:
    await _submit_input(
        page,
        selector=EMAIL_INPUT_SELECTOR,
        text=email,
        error_message="failed to locate the email input",
        continue_cb=continue_cb,
    )


async def submit_password_input(page: Any, password: str, *, continue_cb: Callable[[], Awaitable[None]]) -> None:
    await _submit_input(
        page,
        selector=PASSWORD_INPUT_SELECTOR,
        text=password,
        error_message="failed to locate the password input",
        continue_cb=continue_cb,
    )


async def submit_verification_code_input(page: Any, code: str, *, continue_cb: Callable[[], Awaitable[None]]) -> None:
    await _submit_input(
        page,
        selector=VERIFICATION_CODE_INPUT_SELECTOR,
        text=code,
        error_message="failed to locate the verification code input",
        continue_cb=continue_cb,
    )


async def click_first_continue_button(page: Any) -> None:
    for selector in CONTINUE_BUTTON_SELECTORS:
        try:
            locator = page.locator(selector).first
            if await locator.count() == 0:
                continue
            await human_click_locator(page=page, locator=locator)
            await asyncio.sleep(NAVIGATION_DELAY_SECONDS)
            return
        except Exception:
            continue
    raise RuntimeError("failed to locate a continue button")


async def _submit_input(
    page: Any,
    *,
    selector: str,
    text: str,
    error_message: str,
    continue_cb: Callable[[], Awaitable[None]],
) -> None:
    field = await page.wait_for_selector(selector, timeout=10_000)
    if field is None:
        raise RuntimeError(error_message)
    await human_type_locator(page=page, locator=field, text=text)
    await asyncio.sleep(ACTION_DELAY_SECONDS)
    await continue_cb()
