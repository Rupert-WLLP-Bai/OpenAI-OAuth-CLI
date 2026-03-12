from __future__ import annotations

from typing import Protocol, cast

from openai_auth_core.flow import OAuthLoginDriver, run_oauth_login_flow

from .mailbox import VerificationCodeProvider
from .models import AccountRecord


class BrowserDriver(Protocol):
    async def open_authorization_page(self, auth_url: str) -> None: ...
    async def current_state(self) -> str: ...
    async def submit_email(self, email: str) -> None: ...
    async def submit_password(self, password: str) -> None: ...
    async def submit_verification_code(self, code: str) -> None: ...
    async def click_continue(self) -> None: ...


class LoginStateMachine:
    def __init__(self, *, browser: BrowserDriver, code_provider: VerificationCodeProvider) -> None:
        self.browser = browser
        self.code_provider = code_provider

    async def complete_login(self, *, account: AccountRecord, email: str, password: str, timeout: int) -> str:
        return await run_oauth_login_flow(
            browser=cast(OAuthLoginDriver, self.browser),
            code_provider=self.code_provider,
            account=account,
            email=email,
            password=password,
            timeout=timeout,
            callback_url="",
            callback_done=lambda: False,
        )
