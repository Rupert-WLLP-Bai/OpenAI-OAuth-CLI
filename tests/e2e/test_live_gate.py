from __future__ import annotations

import pytest


@pytest.mark.live_e2e
def test_live_e2e_gate_enables_execution(live_e2e_enabled: bool) -> None:
    assert live_e2e_enabled is True
