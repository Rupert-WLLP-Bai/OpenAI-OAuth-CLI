from __future__ import annotations

import asyncio
import math
from collections.abc import Callable


class FlowDeadline:
    def __init__(self, *, timeout: int, now: Callable[[], float] | None = None) -> None:
        self._now = now or (lambda: asyncio.get_running_loop().time())
        self._deadline = self._now() + timeout

    def expired(self) -> bool:
        return self._now() >= self._deadline

    def remaining_seconds(self) -> float:
        return max(0.0, self._deadline - self._now())

    def remaining_timeout(self) -> int:
        return max(0, math.ceil(self.remaining_seconds()))
