from __future__ import annotations

from typing import TYPE_CHECKING

from openai_auth_core.oauth_pages import classify_oauth_login_state

from .models import AuthPageSignals
from .oauth import build_callback_url

if TYPE_CHECKING:
    from patchright.async_api import Page


def classify_auth_page_state(signals: AuthPageSignals, *, callback_port: int = 1455) -> str:
    return classify_oauth_login_state(
        signals,
        callback_url=build_callback_url(callback_port),
        callback_done=False,
    )


async def extract_auth_page_signals(page: Page) -> AuthPageSignals:
    try:
        title = await page.title()
    except Exception:
        title = ""
    try:
        body_text = (await page.text_content("body")) or ""
    except Exception:
        body_text = ""
    try:
        has_email_input = bool(
            await page.locator('input[type="email"], input[name="username"]:not([type="hidden"]), input[placeholder*="email" i]').count()
        )
    except Exception:
        has_email_input = False
    try:
        has_password_input = bool(
            await page.locator('input[type="password"], input[name="password"]').count()
        )
    except Exception:
        has_password_input = False
    try:
        has_code_input = bool(
            await page.locator(
                'input[placeholder*="code" i], input[name*="code" i], input[type="text"][autocomplete="one-time-code"]'
            ).count()
        )
    except Exception:
        has_code_input = False

    return AuthPageSignals(
        url=page.url,
        title=title,
        body_text=body_text[:2000],
        has_email_input=has_email_input,
        has_password_input=has_password_input,
        has_code_input=has_code_input,
    )
