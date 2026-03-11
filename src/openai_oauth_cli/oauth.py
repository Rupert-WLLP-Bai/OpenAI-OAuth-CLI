from __future__ import annotations

from openai_auth_core.oauth import (
    build_auth_url,
    build_callback_url,
    build_token_exchange_payload,
    make_pkce_material,
)
from openai_auth_core.oauth import exchange_code_for_tokens as _exchange_code_for_tokens
from openai_auth_core.oauth import parse_callback_url as _parse_callback_url

from .models import TokenBundle


def parse_callback_url(callback_url: str, *, expected_state: str) -> str:
    try:
        return _parse_callback_url(callback_url, expected_state=expected_state)
    except RuntimeError as exc:
        raise ValueError(str(exc)) from exc


async def exchange_code_for_tokens(
    *,
    code: str,
    code_verifier: str,
    redirect_uri: str,
    proxy: str | None = None,
) -> TokenBundle:
    bundle = await _exchange_code_for_tokens(
        code=code,
        code_verifier=code_verifier,
        redirect_uri=redirect_uri,
        proxy=proxy,
    )
    return TokenBundle(
        refresh_token=bundle.refresh_token,
        access_token=bundle.access_token,
        id_token=bundle.id_token,
    )


__all__ = [
    "build_auth_url",
    "build_callback_url",
    "build_token_exchange_payload",
    "exchange_code_for_tokens",
    "make_pkce_material",
    "parse_callback_url",
]
