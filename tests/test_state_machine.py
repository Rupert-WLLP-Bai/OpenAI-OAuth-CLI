from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from openai_oauth_cli.models import AccountRecord
from openai_oauth_cli.state_machine import LoginStateMachine


@dataclass
class FakeBrowser:
    states: list[str]
    callback_url: str | None = None

    def __post_init__(self) -> None:
        self.email_submitted = False
        self.password_submitted = False
        self.codes: list[str] = []
        self.continue_clicks = 0
        self._index = 0

    async def open_authorization_page(self, auth_url: str) -> None:
        self.opened_url = auth_url

    async def current_state(self) -> str:
        if self.callback_url:
            return "callback"
        state = self.states[min(self._index, len(self.states) - 1)]
        return state

    async def submit_email(self, email: str) -> None:
        self.email_submitted = True
        self._index += 1

    async def submit_password(self, password: str) -> None:
        self.password_submitted = True
        self._index += 1

    async def submit_verification_code(self, code: str) -> None:
        self.codes.append(code)
        self._index += 1

    async def click_continue(self) -> None:
        self.continue_clicks += 1
        self._index += 1


class FakeCodeProvider:
    def __init__(self, code: str = "123456") -> None:
        self.code = code
        self.calls = 0

    async def get_code(self, *, account: AccountRecord, timeout: int) -> str | None:
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


def test_state_machine_handles_verification_and_consent() -> None:
    browser = FakeBrowser(states=["email", "password", "verification_code", "consent", "callback"])
    provider = FakeCodeProvider()
    account = AccountRecord(email="a@example.com", mail_client_id="uuid", mail_refresh_token="rt", group="g")
    machine = LoginStateMachine(browser=browser, code_provider=provider)

    result = asyncio.run(machine.complete_login(account=account, email="a@example.com", password="pw", timeout=5))

    assert result == "callback"
    assert browser.email_submitted is True
    assert browser.password_submitted is True
    assert browser.codes == ["123456"]
    assert browser.continue_clicks == 1


def test_state_machine_raises_on_error_state() -> None:
    browser = FakeBrowser(states=["email", "error"])
    provider = FakeCodeProvider()
    account = AccountRecord(email="a@example.com", mail_client_id="uuid", mail_refresh_token="rt", group="g")
    machine = LoginStateMachine(browser=browser, code_provider=provider)

    with pytest.raises(RuntimeError, match="error state"):
        asyncio.run(machine.complete_login(account=account, email="a@example.com", password="pw", timeout=5))


def test_state_machine_does_not_resubmit_email_while_waiting_for_transition() -> None:
    class StickyEmailBrowser(FakeBrowser):
        def __post_init__(self) -> None:
            super().__post_init__()
            self.email_submit_count = 0

        async def submit_email(self, email: str) -> None:
            self.email_submit_count += 1
            self.email_submitted = True

        async def current_state(self) -> str:
            if self._index < 2:
                self._index += 1
                return "email"
            return "callback"

    browser = StickyEmailBrowser(states=["email"])
    provider = FakeCodeProvider()
    account = AccountRecord(email="a@example.com", mail_client_id="uuid", mail_refresh_token="rt", group="g")
    machine = LoginStateMachine(browser=browser, code_provider=provider)

    asyncio.run(machine.complete_login(account=account, email="a@example.com", password="pw", timeout=5))

    assert browser.email_submitted is True
    assert browser.password_submitted is False
    assert browser.email_submit_count == 1


def test_state_machine_passes_remaining_timeout_to_code_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: list[int] = []
    loop = FakeLoop([100.0, 101.0, 103.0, 103.0, 104.0])

    class ObservingCodeProvider:
        async def get_code(self, *, account: AccountRecord, timeout: int) -> str | None:
            observed.append(timeout)
            return "123456"

    monkeypatch.setattr("openai_auth_core.flow.asyncio.get_running_loop", lambda: loop)

    browser = FakeBrowser(states=["email", "verification_code", "callback"])
    account = AccountRecord(email="a@example.com", mail_client_id="uuid", mail_refresh_token="rt", group="g")
    machine = LoginStateMachine(browser=browser, code_provider=ObservingCodeProvider())

    result = asyncio.run(machine.complete_login(account=account, email="a@example.com", password="pw", timeout=5))

    assert result == "callback"
    assert observed == [2]


def test_state_machine_sleeps_while_waiting_for_transition(monkeypatch: pytest.MonkeyPatch) -> None:
    sleep_calls: list[float] = []
    loop = FakeLoop([100.0, 100.1, 100.2, 105.1])

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr("openai_auth_core.flow.asyncio.get_running_loop", lambda: loop)
    monkeypatch.setattr("openai_auth_core.flow.asyncio.sleep", fake_sleep)

    browser = FakeBrowser(states=["email", "email"])
    account = AccountRecord(email="a@example.com", mail_client_id="uuid", mail_refresh_token="rt", group="g")
    machine = LoginStateMachine(browser=browser, code_provider=FakeCodeProvider())

    with pytest.raises(RuntimeError, match="timed out"):
        asyncio.run(machine.complete_login(account=account, email="a@example.com", password="pw", timeout=5))

    assert sleep_calls == [0.1]


def test_state_machine_delegates_to_shared_oauth_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    browser = FakeBrowser(states=["email"])
    provider = FakeCodeProvider()
    account = AccountRecord(email="a@example.com", mail_client_id="uuid", mail_refresh_token="rt", group="g")
    machine = LoginStateMachine(browser=browser, code_provider=provider)
    captured: dict[str, object] = {}

    async def fake_run_oauth_login_flow(**kwargs: object) -> str:
        captured.update(kwargs)
        return "callback"

    monkeypatch.setattr("openai_oauth_cli.state_machine.run_oauth_login_flow", fake_run_oauth_login_flow, raising=False)

    result = asyncio.run(machine.complete_login(account=account, email="a@example.com", password="pw", timeout=5))

    assert result == "callback"
    assert captured["browser"] is browser
    assert captured["code_provider"] is provider
    assert captured["account"] is account
    assert captured["email"] == "a@example.com"
    assert captured["password"] == "pw"
    assert captured["timeout"] == 5
