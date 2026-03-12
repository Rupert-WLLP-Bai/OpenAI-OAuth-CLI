from __future__ import annotations

import asyncio
import hashlib
import re
from datetime import date, timedelta
from typing import cast

from openai_auth_core.flow import FlowDeadline, OAuthLoginDriver, run_oauth_login_flow

from .diagnostics import RunLogger
from .models import MailAccountRecord, OAuthLoginBrowser, RegistrationBrowser, VerificationCodeProvider


WAIT_FOR_TRANSITION_DELAY_SECONDS = 0.1


def derive_full_name(email: str) -> str:
    local_part = email.split("@", 1)[0]
    tokens = [token for token in re.split(r"[._-]+", local_part) if token]
    cleaned: list[str] = []
    for token in tokens:
        letters_only = re.sub(r"\d+", "", token)
        if letters_only:
            cleaned.append(letters_only.capitalize())
        if len(cleaned) == 2:
            break
    if cleaned:
        return " ".join(cleaned)
    return "Openai User"


def derive_birthday(email: str) -> date:
    normalized = email.strip().casefold().encode("utf-8")
    start = date(1990, 1, 1)
    end = date(2001, 12, 31)
    span_days = (end - start).days
    offset = int(hashlib.sha256(normalized).hexdigest()[:8], 16) % (span_days + 1)
    return start + timedelta(days=offset)


class RegistrationStateMachine:
    derive_full_name = staticmethod(derive_full_name)
    derive_birthday = staticmethod(derive_birthday)

    def __init__(self, *, browser: RegistrationBrowser, code_provider: VerificationCodeProvider) -> None:
        self.browser = browser
        self.code_provider = code_provider

    async def complete_registration(
        self,
        *,
        account: MailAccountRecord,
        email: str,
        password: str,
        timeout: int,
    ) -> str:
        deadline = FlowDeadline(timeout=timeout)
        last_state = ""
        handled_once = False

        while not deadline.expired():
            state = await self.browser.current_state()
            if state != last_state:
                last_state = state
                handled_once = False

            if state == "landing":
                if not handled_once:
                    await self.browser.click_signup()
                    handled_once = True
                else:
                    await asyncio.sleep(WAIT_FOR_TRANSITION_DELAY_SECONDS)
                continue
            if state == "email":
                if not handled_once:
                    await self.browser.submit_email(email)
                    handled_once = True
                else:
                    await asyncio.sleep(WAIT_FOR_TRANSITION_DELAY_SECONDS)
                continue
            if state == "password_optional":
                if not handled_once:
                    await self.browser.submit_password(password)
                    handled_once = True
                else:
                    await asyncio.sleep(WAIT_FOR_TRANSITION_DELAY_SECONDS)
                continue
            if state == "verification_code":
                if not handled_once:
                    remaining_timeout = deadline.remaining_timeout()
                    code = await self.code_provider.get_code(account=account, timeout=remaining_timeout)
                    if not code:
                        raise RuntimeError("verification code required but unavailable")
                    await self.browser.submit_verification_code(code)
                    handled_once = True
                else:
                    await asyncio.sleep(WAIT_FOR_TRANSITION_DELAY_SECONDS)
                continue
            if state == "about_you":
                if not handled_once:
                    await self.browser.submit_profile(
                        self.derive_full_name(email),
                        self.derive_birthday(email),
                    )
                    handled_once = True
                else:
                    await asyncio.sleep(WAIT_FOR_TRANSITION_DELAY_SECONDS)
                continue
            if state == "success":
                return "success"
            if state == "error":
                raise RuntimeError("registration entered error state")
            await asyncio.sleep(0.1)

        raise RuntimeError("registration timed out before reaching success state")


class OAuthLoginVerifier:
    def __init__(
        self,
        *,
        browser: OAuthLoginBrowser,
        code_provider: VerificationCodeProvider,
        logger: RunLogger | None = None,
    ) -> None:
        self.browser = browser
        self.code_provider = code_provider
        self.logger = logger

    async def complete_login(
        self,
        *,
        account: MailAccountRecord,
        email: str,
        password: str,
        timeout: int,
        callback_url: str,
        callback_task: object,
    ) -> str:
        return await run_oauth_login_flow(
            browser=cast(OAuthLoginDriver, self.browser),
            code_provider=self.code_provider,
            account=account,
            email=email,
            password=password,
            timeout=timeout,
            callback_url=callback_url,
            callback_done=getattr(callback_task, "done", lambda: False),
            on_state_change=self._log_oauth_state_change,
            on_error=self._capture_verify_login_error,
        )

    def _log_oauth_state_change(self, state: str) -> None:
        if self.logger is not None:
            self.logger.log_event("oauth_state_change", state=state)

    async def _capture_verify_login_error(self) -> None:
        await self.browser.capture_debug_artifacts("verify-login-error")
