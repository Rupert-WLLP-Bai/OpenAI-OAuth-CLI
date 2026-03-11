from __future__ import annotations

import pytest

from openai_auth_core.oauth import (
    build_auth_url,
    build_callback_url,
    build_token_exchange_payload,
    make_pkce_material,
    parse_callback_url,
    validate_callback_result,
)


def test_auth_core_build_auth_url_contains_redirect_uri() -> None:
    _, challenge, state = make_pkce_material()

    url = build_auth_url(callback_port=1455, code_challenge=challenge, state=state)

    assert "redirect_uri=http%3A%2F%2Flocalhost%3A1455%2Fauth%2Fcallback" in url


def test_auth_core_parse_callback_url_validates_state() -> None:
    callback_url = build_callback_url(1455) + "?code=abc123&state=expected"

    assert parse_callback_url(callback_url, expected_state="expected") == "abc123"

    with pytest.raises(RuntimeError, match="state mismatch"):
        parse_callback_url(callback_url, expected_state="wrong")


def test_auth_core_validate_callback_result_rejects_mismatch() -> None:
    with pytest.raises(RuntimeError, match="state mismatch"):
        validate_callback_result(code="abc123", state="wrong", expected_state="expected")


def test_auth_core_token_payload_uses_form_fields() -> None:
    payload = build_token_exchange_payload(
        code="abc123",
        code_verifier="verifier",
        redirect_uri=build_callback_url(1455),
    )

    assert payload["grant_type"] == "authorization_code"
    assert payload["client_id"]
    assert payload["code"] == "abc123"
    assert payload["code_verifier"] == "verifier"
