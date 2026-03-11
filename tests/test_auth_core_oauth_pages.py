from __future__ import annotations

from types import SimpleNamespace

from openai_auth_core.oauth_pages import classify_oauth_login_state, summarize_oauth_error


def test_auth_core_oauth_pages_detects_consent_page() -> None:
    signals = SimpleNamespace(
        url="https://auth.openai.com/sign-in-with-chatgpt/codex/consent",
        title="Sign in to Codex with ChatGPT - OpenAI",
        body_text="Continue",
        has_email_input=False,
        has_password_input=False,
        has_code_input=False,
    )

    assert classify_oauth_login_state(
        signals,
        callback_url="http://localhost:1455/auth/callback",
        callback_done=False,
    ) == "consent"


def test_auth_core_oauth_pages_summarizes_incorrect_password() -> None:
    signals = SimpleNamespace(
        url="https://auth.openai.com/log-in/password",
        title="Enter your password - OpenAI",
        body_text="Incorrect email address or password",
        has_email_input=False,
        has_password_input=True,
        has_code_input=False,
    )

    assert summarize_oauth_error(signals) == "openai auth error page: incorrect email address or password"
