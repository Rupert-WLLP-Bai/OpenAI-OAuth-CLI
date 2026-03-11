from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AccountRecord:
    email: str
    mail_client_id: str
    mail_refresh_token: str
    group: str = ""
    is_registered: bool = False
    is_primary: bool = False


@dataclass(frozen=True)
class TokenBundle:
    refresh_token: str
    access_token: str = ""
    id_token: str = ""


@dataclass(frozen=True)
class AuthPageSignals:
    url: str
    title: str = ""
    body_text: str = ""
    has_email_input: bool = False
    has_password_input: bool = False
    has_code_input: bool = False
