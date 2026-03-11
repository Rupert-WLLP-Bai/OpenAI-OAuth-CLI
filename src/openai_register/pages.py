from __future__ import annotations

from typing import TYPE_CHECKING

from openai_auth_core.oauth_pages import classify_oauth_login_state, summarize_oauth_error

from .models import OAuthPageSignals, RegistrationPageSignals, RegistrationState

if TYPE_CHECKING:
    from patchright.async_api import Page


def classify_registration_state(signals: RegistrationPageSignals) -> RegistrationState:
    normalized_url = signals.url.casefold()
    combined_text = f"{signals.title}\n{signals.body_text}".casefold()

    if (
        (signals.has_prompt_textarea or "有问题，尽管问" in combined_text)
        and not signals.has_signup_button
        and not signals.has_email_input
        and "登录或注册" not in combined_text
    ):
        return "success"
    if (
        "oops, an error occurred" in combined_text
        or "operation timed out" in combined_text
        or "无法根据该信息创建帐户" in combined_text
    ):
        return "error"
    if (signals.has_profile_name_input and signals.has_birthday_field) or "/about-you" in normalized_url:
        return "about_you"
    if signals.has_code_input or "email-verification" in normalized_url:
        return "verification_code"
    if signals.has_password_input or "/log-in/password" in normalized_url:
        return "password_optional"
    if signals.has_email_input or "登录或注册" in combined_text:
        return "email"
    if signals.has_signup_button or "免费注册" in combined_text:
        return "landing"
    return "unknown"


async def extract_registration_page_signals(page: Page) -> RegistrationPageSignals:
    try:
        title = await page.title()
    except Exception:
        title = ""
    try:
        body_text = (await page.text_content("body")) or ""
    except Exception:
        body_text = ""
    return RegistrationPageSignals(
        url=page.url,
        title=title,
        body_text=body_text[:2000],
        has_signup_button=await _has_match(page, '[data-testid="signup-button"], button:has-text("免费注册"), button:has-text("Sign up")'),
        has_email_input=await _has_match(
            page,
            'input[type="email"], input[name="username"]:not([type="hidden"]), input[placeholder*="email" i], input[placeholder*="电子邮件" i]',
        ),
        has_password_input=await _has_match(page, 'input[type="password"], input[name="password"]'),
        has_code_input=await _has_match(
            page,
            'input[autocomplete="one-time-code"], input[placeholder*="验证码" i], input[placeholder*="code" i]',
        ),
        has_profile_name_input=await _has_match(
            page,
            'input[autocomplete="name"], input[name="name"], input[placeholder*="全名" i]',
        ),
        has_birthday_field=await _has_match(page, '[data-type="year"][role="spinbutton"], input[name="birthday"]'),
        has_prompt_textarea=await _has_match(page, '#prompt-textarea, textarea[name="prompt-textarea"]'),
    )


async def extract_oauth_page_signals(page: Page) -> OAuthPageSignals:
    try:
        title = await page.title()
    except Exception:
        title = ""
    try:
        body_text = (await page.text_content("body")) or ""
    except Exception:
        body_text = ""
    return OAuthPageSignals(
        url=page.url,
        title=title,
        body_text=body_text[:2000],
        has_email_input=await _has_match(
            page,
            'input[type="email"], input[name="username"]:not([type="hidden"]), input[placeholder*="email" i], input[placeholder*="电子邮件" i]',
        ),
        has_password_input=await _has_match(page, 'input[type="password"], input[name="password"]'),
        has_code_input=await _has_match(
            page,
            'input[autocomplete="one-time-code"], input[placeholder*="验证码" i], input[placeholder*="code" i]',
        ),
    )


async def _has_match(page: Page, selector: str) -> bool:
    try:
        return await page.locator(selector).count() > 0
    except Exception:
        return False


__all__ = [
    "classify_oauth_login_state",
    "classify_registration_state",
    "extract_oauth_page_signals",
    "extract_registration_page_signals",
    "summarize_oauth_error",
]
