from __future__ import annotations

from pathlib import Path


_ADMIN_SHELL_PATH = Path(__file__).resolve().parent / "static" / "admin" / "index.html"


def render_admin_shell() -> str:
    return _ADMIN_SHELL_PATH.read_text(encoding="utf-8")
