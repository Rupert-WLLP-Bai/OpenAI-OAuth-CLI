from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal, Protocol, runtime_checkable


@dataclass(frozen=True)
class MailAccountRecord:
    email: str
    mail_client_id: str
    mail_refresh_token: str


@dataclass(frozen=True)
class RegistrationAccountRecord:
    email: str
    mail_client_id: str
    mail_refresh_token: str
    is_registered: bool
    registered_at: str | None = None
    last_registration_attempt_at: str | None = None
    last_registration_error: str = ""


@dataclass(frozen=True)
class RegistrationPageSignals:
    url: str
    title: str = ""
    body_text: str = ""
    has_signup_button: bool = False
    has_email_input: bool = False
    has_password_input: bool = False
    has_code_input: bool = False
    has_profile_name_input: bool = False
    has_birthday_field: bool = False
    has_prompt_textarea: bool = False


@dataclass(frozen=True)
class OAuthPageSignals:
    url: str
    title: str = ""
    body_text: str = ""
    has_email_input: bool = False
    has_password_input: bool = False
    has_code_input: bool = False


RegistrationState = Literal[
    "landing",
    "email",
    "password_optional",
    "verification_code",
    "about_you",
    "success",
    "error",
    "unknown",
]


OAuthLoginState = Literal[
    "email",
    "password",
    "verification_code",
    "consent",
    "callback",
    "error",
    "unknown",
]


@runtime_checkable
class VerificationCodeProvider(Protocol):
    async def get_code(self, *, account: MailAccountRecord, timeout: int) -> str | None: ...


@runtime_checkable
class RegistrationBrowser(Protocol):
    async def open_chatgpt(self) -> None: ...
    async def current_state(self) -> RegistrationState: ...
    async def click_signup(self) -> None: ...
    async def submit_email(self, email: str) -> None: ...
    async def submit_password(self, password: str) -> None: ...
    async def submit_verification_code(self, code: str) -> None: ...
    async def submit_profile(self, full_name: str, birthday: date) -> None: ...


@runtime_checkable
class OAuthLoginBrowser(Protocol):
    async def open_authorization_page(self, auth_url: str) -> None: ...
    async def current_oauth_state(self, *, callback_url: str, callback_done: bool) -> OAuthLoginState: ...
    async def submit_email(self, email: str) -> None: ...
    async def submit_password(self, password: str) -> None: ...
    async def submit_verification_code(self, code: str) -> None: ...
    async def click_continue(self) -> None: ...
    async def capture_debug_artifacts(self, label: str) -> None: ...
    def get_oauth_error_message(self) -> str: ...
