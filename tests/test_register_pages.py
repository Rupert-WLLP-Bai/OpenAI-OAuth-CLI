from __future__ import annotations

from datetime import date
from typing import get_args

from openai_register.models import OAuthPageSignals, RegistrationPageSignals, RegistrationState
from openai_register.pages import classify_oauth_login_state, classify_registration_state, summarize_oauth_error
from openai_register.state_machine import derive_birthday, derive_full_name


def test_registration_state_literal_covers_registration_flow_states() -> None:
    assert get_args(RegistrationState) == (
        "landing",
        "email",
        "password_optional",
        "verification_code",
        "about_you",
        "success",
        "error",
        "unknown",
    )


def test_classify_registration_state_detects_landing_page() -> None:
    signals = RegistrationPageSignals(
        url="https://chatgpt.com/",
        body_text="免费注册",
        has_signup_button=True,
    )

    assert classify_registration_state(signals) == "landing"


def test_classify_registration_state_detects_verification_page() -> None:
    signals = RegistrationPageSignals(
        url="https://auth.openai.com/email-verification",
        title="检查您的收件箱 - OpenAI",
        has_code_input=True,
    )

    assert classify_registration_state(signals) == "verification_code"


def test_classify_registration_state_detects_about_you_page() -> None:
    signals = RegistrationPageSignals(
        url="https://auth.openai.com/about-you",
        has_profile_name_input=True,
        has_birthday_field=True,
    )

    assert classify_registration_state(signals) == "about_you"


def test_classify_registration_state_detects_success_page() -> None:
    signals = RegistrationPageSignals(
        url="https://chatgpt.com/",
        body_text="有问题，尽管问",
        has_prompt_textarea=True,
    )

    assert classify_registration_state(signals) == "success"


def test_classify_registration_state_does_not_treat_public_homepage_as_success() -> None:
    signals = RegistrationPageSignals(
        url="https://chatgpt.com/",
        body_text="有问题，尽管问 免费注册 登录或注册",
        has_prompt_textarea=True,
        has_signup_button=True,
        has_email_input=True,
    )

    assert classify_registration_state(signals) == "email"


def test_classify_registration_state_prefers_email_when_auth_modal_is_already_open() -> None:
    signals = RegistrationPageSignals(
        url="https://chatgpt.com/",
        body_text="免费注册 登录或注册",
        has_signup_button=True,
        has_email_input=True,
    )

    assert classify_registration_state(signals) == "email"


def test_derive_full_name_from_email_local_part() -> None:
    assert derive_full_name("garrett.henegar1988@example.com") == "Garrett Henegar"


def test_derive_birthday_is_deterministic_and_in_range() -> None:
    birthday = derive_birthday("garrett.henegar1988@example.com")

    assert date(1990, 1, 1) <= birthday <= date(2001, 12, 31)
    assert birthday == derive_birthday("garrett.henegar1988@example.com")


def test_classify_oauth_login_state_treats_incorrect_password_as_error() -> None:
    signals = OAuthPageSignals(
        url="https://auth.openai.com/log-in/password",
        title="Enter your password - OpenAI",
        body_text="Incorrect email address or password",
        has_password_input=True,
    )

    assert classify_oauth_login_state(
        signals,
        callback_url="http://localhost:1455/auth/callback",
        callback_done=False,
    ) == "error"
    assert summarize_oauth_error(signals) == "openai auth error page: incorrect email address or password"
