from __future__ import annotations

from openai_register.browser import detect_oauth_response_error


def test_detect_oauth_response_error_treats_password_verify_401_as_incorrect_password() -> None:
    assert detect_oauth_response_error(
        url="https://auth.openai.com/api/accounts/password/verify",
        status=401,
        method="POST",
    ) == "openai auth error page: incorrect email address or password"


def test_detect_oauth_response_error_ignores_non_auth_responses() -> None:
    assert detect_oauth_response_error(
        url="https://chatgpt.com/",
        status=200,
        method="GET",
    ) is None
