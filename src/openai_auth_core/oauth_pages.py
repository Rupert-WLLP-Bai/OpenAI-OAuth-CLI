from __future__ import annotations

from typing import Protocol


class OAuthPageSignalsLike(Protocol):
    url: str
    title: str
    body_text: str
    has_email_input: bool
    has_password_input: bool
    has_code_input: bool


def classify_oauth_login_state(
    signals: OAuthPageSignalsLike,
    *,
    callback_url: str,
    callback_done: bool,
) -> str:
    normalized_url = signals.url.casefold()
    combined_text = f"{signals.title}\n{signals.body_text}".casefold()

    if callback_done or (signals.url.startswith(callback_url) and ("code=" in signals.url or "error=" in signals.url)):
        return "callback"
    if (
        "incorrect email address or password" in combined_text
        or "incorrect password" in combined_text
        or "oops, an error occurred" in combined_text
        or "operation timed out" in combined_text
    ):
        return "error"
    if signals.has_password_input or "/log-in/password" in normalized_url:
        return "password"
    if signals.has_code_input or "email-verification" in normalized_url:
        return "verification_code"
    if "sign-in-with-chatgpt/codex/consent" in normalized_url or "sign in to codex with chatgpt" in combined_text:
        return "consent"
    if signals.has_email_input:
        return "email"
    return "unknown"


def summarize_oauth_error(signals: OAuthPageSignalsLike) -> str:
    combined_text = f"{signals.title}\n{signals.body_text}".casefold()

    if "incorrect email address or password" in combined_text:
        return "openai auth error page: incorrect email address or password"
    if "incorrect password" in combined_text:
        return "openai auth error page: incorrect password"
    if "operation timed out" in combined_text:
        return "openai auth error page: operation timed out"
    if "oops, an error occurred" in combined_text:
        return "openai auth error page: oops, an error occurred"
    title = signals.title.strip()
    if title:
        return f"openai auth error page: {title}"
    return "login entered error state"
