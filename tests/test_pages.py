from __future__ import annotations

from openai_oauth_cli.models import AuthPageSignals
from openai_oauth_cli.pages import classify_auth_page_state


def test_classify_auth_page_state_detects_password_page() -> None:
    signals = AuthPageSignals(url="https://auth.openai.com/log-in/password", has_password_input=True)

    assert classify_auth_page_state(signals) == "password"


def test_classify_auth_page_state_detects_consent_page() -> None:
    signals = AuthPageSignals(
        url="https://auth.openai.com/sign-in-with-chatgpt/codex/consent",
        title="Sign in to Codex with ChatGPT - OpenAI",
        body_text="Continue",
    )

    assert classify_auth_page_state(signals) == "consent"


def test_classify_auth_page_state_detects_error_page() -> None:
    signals = AuthPageSignals(
        url="https://auth.openai.com/log-in",
        title="Oops, an error occurred! - OpenAI",
        body_text="Operation timed out",
    )

    assert classify_auth_page_state(signals) == "error"
