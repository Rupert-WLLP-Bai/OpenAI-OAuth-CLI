from __future__ import annotations

import asyncio
from typing import Any


HUMAN_TYPE_DELAY_MS = 90
HUMAN_MOUSE_STEPS = 12


async def human_click_locator(*, page: Any, locator: Any) -> None:
    await locator.scroll_into_view_if_needed()
    await locator.hover()
    box = await locator.bounding_box()
    if box is None:
        raise RuntimeError("failed to read element position for human click")

    center_x = float(box["x"]) + float(box["width"]) / 2
    center_y = float(box["y"]) + float(box["height"]) / 2
    await page.mouse.move(center_x - 24, center_y - 10, steps=HUMAN_MOUSE_STEPS // 2)
    await asyncio.sleep(0.08)
    await page.mouse.move(center_x, center_y, steps=HUMAN_MOUSE_STEPS)
    await asyncio.sleep(0.05)
    await page.mouse.click(center_x, center_y)


async def human_type_locator(*, page: Any, locator: Any, text: str) -> None:
    await locator.scroll_into_view_if_needed()
    await locator.focus()
    await asyncio.sleep(0.06)
    await page.keyboard.press("Control+A")
    await asyncio.sleep(0.04)
    await page.keyboard.type(text, delay=HUMAN_TYPE_DELAY_MS)
