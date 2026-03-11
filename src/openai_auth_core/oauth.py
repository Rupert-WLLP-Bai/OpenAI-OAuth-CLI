from __future__ import annotations

import base64
import hashlib
import json
import secrets
import urllib.parse
from dataclasses import dataclass

import aiohttp


OPENAI_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
OPENAI_AUTH_URL = "https://auth.openai.com/oauth/authorize"
OPENAI_TOKEN_URL = "https://auth.openai.com/oauth/token"
OPENAI_SCOPE = "openid email profile offline_access"


@dataclass(frozen=True)
class TokenBundle:
    refresh_token: str
    access_token: str = ""
    id_token: str = ""


def build_callback_url(callback_port: int) -> str:
    return f"http://localhost:{callback_port}/auth/callback"


def make_pkce_material() -> tuple[str, str, str]:
    code_verifier = secrets.token_urlsafe(72)
    challenge_bytes = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    code_challenge = base64.urlsafe_b64encode(challenge_bytes).decode("ascii").rstrip("=")
    state = secrets.token_urlsafe(32)
    return code_verifier, code_challenge, state


def build_auth_url(*, callback_port: int, code_challenge: str, state: str) -> str:
    params = urllib.parse.urlencode(
        {
            "client_id": OPENAI_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": build_callback_url(callback_port),
            "scope": OPENAI_SCOPE,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "prompt": "login",
            "id_token_add_organizations": "true",
            "codex_cli_simplified_flow": "true",
        }
    )
    return f"{OPENAI_AUTH_URL}?{params}"


def validate_callback_result(
    *,
    code: str,
    state: str,
    expected_state: str,
    error: str = "",
    error_description: str = "",
) -> None:
    if error:
        raise RuntimeError(f"oauth error: {error} {error_description}".strip())
    if not code:
        raise RuntimeError("missing authorization code")
    if state != expected_state:
        raise RuntimeError("state mismatch")


def parse_callback_url(callback_url: str, *, expected_state: str) -> str:
    parsed = urllib.parse.urlparse(callback_url)
    params = urllib.parse.parse_qs(parsed.query)

    code = str(params.get("code", [""])[0])
    state = str(params.get("state", [""])[0])
    error = str(params.get("error", [""])[0])
    error_description = str(params.get("error_description", [""])[0])

    validate_callback_result(
        code=code,
        state=state,
        expected_state=expected_state,
        error=error,
        error_description=error_description,
    )
    return code


def build_token_exchange_payload(*, code: str, code_verifier: str, redirect_uri: str) -> dict[str, str]:
    return {
        "grant_type": "authorization_code",
        "client_id": OPENAI_CLIENT_ID,
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
    }


async def exchange_code_for_tokens(
    *,
    code: str,
    code_verifier: str,
    redirect_uri: str,
    proxy: str | None = None,
) -> TokenBundle:
    payload = build_token_exchange_payload(
        code=code,
        code_verifier=code_verifier,
        redirect_uri=redirect_uri,
    )

    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(
            OPENAI_TOKEN_URL,
            data=payload,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            proxy=proxy,
        ) as response:
            body = await response.text()
            if response.status != 200:
                raise RuntimeError(f"token exchange failed with status {response.status}: {body[:400]}")
            data = json.loads(body)

    refresh_token = str(data.get("refresh_token", "")).strip()
    if not refresh_token:
        raise RuntimeError("token exchange response did not include refresh_token")

    return TokenBundle(
        refresh_token=refresh_token,
        access_token=str(data.get("access_token", "")),
        id_token=str(data.get("id_token", "")),
    )
