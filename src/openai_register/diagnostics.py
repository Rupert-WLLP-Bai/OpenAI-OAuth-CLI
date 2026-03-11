from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime, timezone
import json
from pathlib import Path
import re
from typing import Any


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slugify_email(email: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", email.strip().casefold()).strip("-") or "unknown"


def _normalize(value: Any) -> Any:
    if is_dataclass(value):
        return _normalize(asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    return value


class RunLogger:
    def __init__(self, *, base_dir: Path, command_name: str, email: str) -> None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        slug = _slugify_email(email)
        self.run_dir = base_dir / f"{command_name}-{slug}-{timestamp}"
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self._events_path = self.run_dir / "events.jsonl"

    def log_event(self, event: str, **fields: Any) -> None:
        payload = {"ts": _utcnow(), "event": event}
        payload.update({key: _normalize(value) for key, value in fields.items()})
        with self._events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            handle.write("\n")

    async def capture_page(self, page: Any, *, label: str) -> None:
        try:
            html = await page.content()
            (self.run_dir / f"{label}.html").write_text(html, encoding="utf-8")
        except Exception as exc:  # pragma: no cover
            self.log_event("artifact_error", label=label, artifact="html", error=str(exc))

        try:
            await page.screenshot(path=str(self.run_dir / f"{label}.png"), full_page=True)
        except Exception as exc:  # pragma: no cover
            self.log_event("artifact_error", label=label, artifact="screenshot", error=str(exc))
