from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

import pytest


def _load_batch_login_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "batch_login.py"
    spec = importlib.util.spec_from_file_location("batch_login_script", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_batch_login_passes_accounts_file_none_to_run_login(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_batch_login_module()
    captured: dict[str, object] = {}

    async def fake_run_login(**kwargs: object) -> str:
        captured.update(kwargs)
        return "rt_example"

    monkeypatch.setattr(module, "run_login", fake_run_login)

    result = asyncio.run(
        module.batch_login(
            emails=["user@example.com"],
            password="pw",
            db_path="/tmp/accounts.sqlite3",
        )
    )

    assert result == {"user@example.com": "rt_example"}
    assert captured["accounts_file"] is None


def test_batch_login_main_keeps_stdout_machine_readable(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_batch_login_module()

    async def fake_batch_login(**kwargs: object) -> dict[str, str | None]:
        return {
            "success@example.com": "rt_success",
            "failed@example.com": None,
        }

    monkeypatch.setattr(module, "batch_login", fake_batch_login)
    monkeypatch.setattr(
        module.sys,
        "argv",
        ["batch_login.py", "--emails", "success@example.com", "failed@example.com", "--password", "pw"],
    )

    exit_code = module.main()
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == "success@example.com:rt_success\n"
    assert "=== 登录结果 ===" not in captured.out
    assert "FAILED" not in captured.out


def test_batch_login_main_keeps_stdout_empty_on_all_failures(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_batch_login_module()

    async def fake_batch_login(**kwargs: object) -> dict[str, str | None]:
        return {
            "failed@example.com": None,
        }

    monkeypatch.setattr(module, "batch_login", fake_batch_login)
    monkeypatch.setattr(
        module.sys,
        "argv",
        ["batch_login.py", "--emails", "failed@example.com", "--password", "pw"],
    )

    exit_code = module.main()
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
