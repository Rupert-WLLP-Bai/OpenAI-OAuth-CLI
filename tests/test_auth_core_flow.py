from __future__ import annotations

from openai_auth_core.flow import FlowDeadline


def test_flow_deadline_reports_remaining_timeout_with_ceiling() -> None:
    times = iter([100.0, 103.1])

    deadline = FlowDeadline(timeout=5, now=lambda: next(times))

    assert deadline.remaining_timeout() == 2


def test_flow_deadline_detects_expiry() -> None:
    times = iter([100.0, 105.1])

    deadline = FlowDeadline(timeout=5, now=lambda: next(times))

    assert deadline.expired() is True
