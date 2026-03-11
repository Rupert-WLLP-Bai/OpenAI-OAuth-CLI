from __future__ import annotations

import json
from pathlib import Path

from openai_register.diagnostics import RunLogger


def test_run_logger_writes_jsonl_events(tmp_path: Path) -> None:
    logger = RunLogger(base_dir=tmp_path, command_name="register", email="user@example.com")

    logger.log_event("state_change", state="email", url="https://chatgpt.com/")

    event_path = logger.run_dir / "events.jsonl"
    lines = event_path.read_text(encoding="utf-8").splitlines()

    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["event"] == "state_change"
    assert payload["state"] == "email"
    assert payload["url"] == "https://chatgpt.com/"
