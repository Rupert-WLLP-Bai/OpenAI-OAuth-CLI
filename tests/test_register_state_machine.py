from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date

import pytest

from openai_register.browser import PatchrightBrowser
from openai_register.models import (
    MailAccountRecord,
    OAuthLoginState,
    OAuthLoginBrowser,
    RegistrationState,
    RegistrationBrowser,
    VerificationCodeProvider,
)
from openai_register.state_machine import OAuthLoginVerifier, RegistrationStateMachine


def _accept_registration_browser(browser: RegistrationBrowser) -> None:
    return None


def _accept_oauth_browser(browser: OAuthLoginBrowser) -> None:
    return None


@dataclass
class FakeBrowser:
    states: list[RegistrationState]

    def __post_init__(self) -> None:
        self._index = 0
        self.email_submissions: list[str] = []
        self.password_submissions: list[str] = []
        self.code_submissions: list[str] = []
        self.profile_submissions: list[tuple[str, date]] = []
        self.signup_clicks = 0

    async def current_state(self) -> RegistrationState:
        return self.states[min(self._index, len(self.states) - 1)]

    async def open_chatgpt(self) -> None:
        return None

    async def click_signup(self) -> None:
        self.signup_clicks += 1
        self._index += 1

    async def submit_email(self, email: str) -> None:
        self.email_submissions.append(email)
        self._index += 1

    async def submit_password(self, password: str) -> None:
        self.password_submissions.append(password)
        self._index += 1

    async def submit_verification_code(self, code: str) -> None:
        self.code_submissions.append(code)
        self._index += 1

    async def submit_profile(self, full_name: str, birthday: date) -> None:
        self.profile_submissions.append((full_name, birthday))
        self._index += 1


class FakeCodeProvider:
    def __init__(self, code: str = "123456") -> None:
        self.code = code
        self.calls = 0

    async def get_code(self, *, account: MailAccountRecord, timeout: int) -> str | None:
        self.calls += 1
        return self.code


class FakeLoop:
    def __init__(self, times: list[float]) -> None:
        self._times = iter(times)
        self._last = times[-1]

    def time(self) -> float:
        try:
            self._last = next(self._times)
        except StopIteration:
            pass
        return self._last


@dataclass
class FakeOAuthBrowser:
    states: list[OAuthLoginState]
    error_message: str = "login entered error state"

    def __post_init__(self) -> None:
        self._index = 0
        self.email_submissions: list[str] = []
        self.password_submissions: list[str] = []
        self.code_submissions: list[str] = []
        self.continue_clicks = 0
        self.captured_labels: list[str] = []

    async def open_authorization_page(self, auth_url: str) -> None:
        return None

    async def current_oauth_state(self, *, callback_url: str, callback_done: bool) -> OAuthLoginState:
        return self.states[min(self._index, len(self.states) - 1)]

    async def submit_email(self, email: str) -> None:
        self.email_submissions.append(email)
        self._index += 1

    async def submit_password(self, password: str) -> None:
        self.password_submissions.append(password)
        self._index += 1

    async def submit_verification_code(self, code: str) -> None:
        self.code_submissions.append(code)
        self._index += 1

    async def click_continue(self) -> None:
        self.continue_clicks += 1
        self._index += 1

    async def capture_debug_artifacts(self, label: str) -> None:
        self.captured_labels.append(label)

    def get_oauth_error_message(self) -> str:
        return self.error_message


def test_fake_test_doubles_match_registration_protocols() -> None:
    assert isinstance(FakeBrowser(states=["landing"]), RegistrationBrowser)
    assert isinstance(FakeCodeProvider(), VerificationCodeProvider)
    assert isinstance(FakeOAuthBrowser(states=["email"]), OAuthLoginBrowser)


def test_patchright_browser_matches_registration_protocols() -> None:
    browser = PatchrightBrowser(proxy=None)

    _accept_registration_browser(browser)
    _accept_oauth_browser(browser)


def test_registration_state_machine_handles_optional_password_and_profile() -> None:
    browser = FakeBrowser(
        states=[
            "landing",
            "email",
            "password_optional",
            "verification_code",
            "about_you",
            "success",
        ]
    )
    code_provider = FakeCodeProvider()
    account = MailAccountRecord(
        email="garrett.henegar1988@example.com",
        mail_client_id="client-id",
        mail_refresh_token="refresh-token",
    )
    machine = RegistrationStateMachine(browser=browser, code_provider=code_provider)

    result = asyncio.run(
        machine.complete_registration(
            account=account,
            email=account.email,
            password="pw",
            timeout=5,
        )
    )

    assert result == "success"
    assert browser.signup_clicks == 1
    assert browser.email_submissions == [account.email]
    assert browser.password_submissions == ["pw"]
    assert browser.code_submissions == ["123456"]
    assert browser.profile_submissions == [("Garrett Henegar", machine.derive_birthday(account.email))]


def test_registration_state_machine_skips_missing_password_step() -> None:
    browser = FakeBrowser(states=["landing", "email", "verification_code", "about_you", "success"])
    code_provider = FakeCodeProvider()
    account = MailAccountRecord(
        email="zoe_smith_1994@example.com",
        mail_client_id="client-id",
        mail_refresh_token="refresh-token",
    )
    machine = RegistrationStateMachine(browser=browser, code_provider=code_provider)

    result = asyncio.run(
        machine.complete_registration(
            account=account,
            email=account.email,
            password="pw",
            timeout=5,
        )
    )

    assert result == "success"
    assert browser.password_submissions == []


def test_registration_state_machine_raises_on_error_state() -> None:
    browser = FakeBrowser(states=["landing", "error"])
    code_provider = FakeCodeProvider()
    account = MailAccountRecord(
        email="zoe_smith_1994@example.com",
        mail_client_id="client-id",
        mail_refresh_token="refresh-token",
    )
    machine = RegistrationStateMachine(browser=browser, code_provider=code_provider)

    with pytest.raises(RuntimeError, match="error state"):
        asyncio.run(
            machine.complete_registration(
                account=account,
                email=account.email,
                password="pw",
                timeout=5,
            )
        )


def test_oauth_login_verifier_captures_artifacts_and_raises_specific_error() -> None:
    browser = FakeOAuthBrowser(states=["email", "error"], error_message="openai auth error page: operation timed out")
    code_provider = FakeCodeProvider()
    account = MailAccountRecord(
        email="zoe_smith_1994@example.com",
        mail_client_id="client-id",
        mail_refresh_token="refresh-token",
    )
    verifier = OAuthLoginVerifier(browser=browser, code_provider=code_provider)

    async def run() -> None:
        callback_task = asyncio.create_task(asyncio.sleep(10))
        try:
            await verifier.complete_login(
                account=account,
                email=account.email,
                password="pw",
                timeout=5,
                callback_url="http://localhost:1455/auth/callback",
                callback_task=callback_task,
            )
        finally:
            callback_task.cancel()

    with pytest.raises(RuntimeError, match="operation timed out"):
        asyncio.run(run())

    assert browser.email_submissions == [account.email]
    assert browser.captured_labels == ["verify-login-error"]


def test_registration_state_machine_passes_remaining_timeout_to_code_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[int] = []
    loop = FakeLoop([100.0, 101.0, 102.0, 104.0, 104.0, 104.5])

    class ObservingCodeProvider:
        async def get_code(self, *, account: MailAccountRecord, timeout: int) -> str | None:
            observed.append(timeout)
            return "123456"

    monkeypatch.setattr("openai_register.state_machine.asyncio.get_running_loop", lambda: loop)

    browser = FakeBrowser(states=["landing", "email", "verification_code", "success"])
    account = MailAccountRecord(
        email="garrett.henegar1988@example.com",
        mail_client_id="client-id",
        mail_refresh_token="refresh-token",
    )
    machine = RegistrationStateMachine(browser=browser, code_provider=ObservingCodeProvider())

    result = asyncio.run(
        machine.complete_registration(
            account=account,
            email=account.email,
            password="pw",
            timeout=5,
        )
    )

    assert result == "success"
    assert observed == [1]


def test_registration_state_machine_sleeps_while_waiting_for_transition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleep_calls: list[float] = []
    loop = FakeLoop([100.0, 100.1, 100.2, 105.1])

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr("openai_register.state_machine.asyncio.get_running_loop", lambda: loop)
    monkeypatch.setattr("openai_register.state_machine.asyncio.sleep", fake_sleep)

    browser = FakeBrowser(states=["landing", "landing"])
    account = MailAccountRecord(
        email="garrett.henegar1988@example.com",
        mail_client_id="client-id",
        mail_refresh_token="refresh-token",
    )
    machine = RegistrationStateMachine(browser=browser, code_provider=FakeCodeProvider())

    with pytest.raises(RuntimeError, match="timed out"):
        asyncio.run(
            machine.complete_registration(
                account=account,
                email=account.email,
                password="pw",
                timeout=5,
            )
        )

    assert sleep_calls == [0.1]


def test_oauth_login_verifier_passes_remaining_timeout_to_code_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[int] = []
    loop = FakeLoop([100.0, 101.0, 104.0, 104.0, 104.5])

    class ObservingCodeProvider:
        async def get_code(self, *, account: MailAccountRecord, timeout: int) -> str | None:
            observed.append(timeout)
            return "123456"

    monkeypatch.setattr("openai_register.state_machine.asyncio.get_running_loop", lambda: loop)

    browser = FakeOAuthBrowser(states=["email", "verification_code", "callback"])
    account = MailAccountRecord(
        email="zoe_smith_1994@example.com",
        mail_client_id="client-id",
        mail_refresh_token="refresh-token",
    )
    verifier = OAuthLoginVerifier(browser=browser, code_provider=ObservingCodeProvider())

    async def run() -> str:
        callback_task = asyncio.create_task(asyncio.sleep(10))
        try:
            return await verifier.complete_login(
                account=account,
                email=account.email,
                password="pw",
                timeout=5,
                callback_url="http://localhost:1455/auth/callback",
                callback_task=callback_task,
            )
        finally:
            callback_task.cancel()

    result = asyncio.run(run())

    assert result == "callback"
    assert observed == [1]


def test_oauth_login_verifier_sleeps_while_waiting_for_transition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleep_calls: list[float] = []
    loop = FakeLoop([100.0, 100.1, 100.2, 105.1])

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr("openai_register.state_machine.asyncio.get_running_loop", lambda: loop)
    monkeypatch.setattr("openai_register.state_machine.asyncio.sleep", fake_sleep)

    browser = FakeOAuthBrowser(states=["email", "email"])
    account = MailAccountRecord(
        email="zoe_smith_1994@example.com",
        mail_client_id="client-id",
        mail_refresh_token="refresh-token",
    )
    verifier = OAuthLoginVerifier(browser=browser, code_provider=FakeCodeProvider())

    async def run() -> None:
        callback_task = asyncio.create_task(asyncio.sleep(10))
        try:
            await verifier.complete_login(
                account=account,
                email=account.email,
                password="pw",
                timeout=5,
                callback_url="http://localhost:1455/auth/callback",
                callback_task=callback_task,
            )
        finally:
            callback_task.cancel()

    with pytest.raises(RuntimeError, match="timed out"):
        asyncio.run(run())

    assert sleep_calls == [0.1]
