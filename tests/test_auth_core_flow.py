from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from openai_auth_core.flow import FlowDeadline, run_oauth_login_flow


def test_oauth_flow_contract_exports_driver_and_runner() -> None:
    from openai_auth_core.flow import OAuthLoginDriver, run_oauth_login_flow

    assert OAuthLoginDriver is not None
    assert callable(run_oauth_login_flow)


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
class FakeBrowser:
    states: list[str]
    error_message: str = "login entered error state"

    def __post_init__(self) -> None:
        self._index = 0
        self.email_submissions: list[str] = []
        self.password_submissions: list[str] = []
        self.code_submissions: list[str] = []
        self.continue_clicks = 0
        self.captured_labels: list[str] = []

    async def current_oauth_state(self, *, callback_url: str, callback_done: bool) -> str:
        del callback_url, callback_done
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


class FakeCodeProvider:
    def __init__(self, code: str = "123456") -> None:
        self.code = code
        self.observed_timeouts: list[int] = []

    async def get_code(self, *, account: object, timeout: int) -> str | None:
        del account
        self.observed_timeouts.append(timeout)
        return self.code


def test_flow_deadline_reports_remaining_timeout_with_ceiling() -> None:
    times = iter([100.0, 103.1])

    deadline = FlowDeadline(timeout=5, now=lambda: next(times))

    assert deadline.remaining_timeout() == 2


def test_flow_deadline_detects_expiry() -> None:
    times = iter([100.0, 105.1])

    deadline = FlowDeadline(timeout=5, now=lambda: next(times))

    assert deadline.expired() is True


def test_run_oauth_login_flow_handles_verification_and_consent(monkeypatch: pytest.MonkeyPatch) -> None:
    loop = FakeLoop([100.0, 101.0, 104.0, 104.0, 104.5, 104.5, 104.8])
    browser = FakeBrowser(states=["email", "password", "verification_code", "consent", "callback"])
    code_provider = FakeCodeProvider()
    state_changes: list[str] = []

    monkeypatch.setattr("openai_auth_core.flow.asyncio.get_running_loop", lambda: loop)

    result = asyncio.run(
        run_oauth_login_flow(
            browser=browser,
            code_provider=code_provider,
            account=object(),
            email="user@example.com",
            password="pw",
            timeout=5,
            callback_url="http://localhost:1455/auth/callback",
            callback_done=lambda: False,
            on_state_change=state_changes.append,
        )
    )

    assert result == "callback"
    assert browser.email_submissions == ["user@example.com"]
    assert browser.password_submissions == ["pw"]
    assert browser.code_submissions == ["123456"]
    assert browser.continue_clicks == 1
    assert code_provider.observed_timeouts == [1]
    assert state_changes == ["email", "password", "verification_code", "consent", "callback"]


def test_run_oauth_login_flow_uses_browser_specific_error_and_error_hook() -> None:
    browser = FakeBrowser(states=["error"], error_message="specific oauth error")
    on_error_calls: list[str] = []

    async def on_error() -> None:
        on_error_calls.append("called")

    with pytest.raises(RuntimeError, match="specific oauth error"):
        asyncio.run(
            run_oauth_login_flow(
                browser=browser,
                code_provider=FakeCodeProvider(),
                account=object(),
                email="user@example.com",
                password="pw",
                timeout=5,
                callback_url="http://localhost:1455/auth/callback",
                callback_done=lambda: False,
                on_error=on_error,
            )
        )

    assert browser.captured_labels == []
    assert on_error_calls == ["called"]
