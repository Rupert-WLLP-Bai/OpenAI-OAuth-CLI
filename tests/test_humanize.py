from __future__ import annotations

import asyncio

from openai_register.humanize import human_click_locator, human_type_locator


class FakeMouse:
    def __init__(self) -> None:
        self.moves: list[tuple[float, float, int]] = []
        self.clicks: list[tuple[float, float]] = []

    async def move(self, x: float, y: float, *, steps: int = 1) -> None:
        self.moves.append((x, y, steps))

    async def click(self, x: float, y: float) -> None:
        self.clicks.append((x, y))


class FakeKeyboard:
    def __init__(self) -> None:
        self.typed: list[tuple[str, int]] = []
        self.presses: list[str] = []

    async def type(self, text: str, *, delay: int = 0) -> None:
        self.typed.append((text, delay))

    async def press(self, key: str) -> None:
        self.presses.append(key)


class FakePage:
    def __init__(self) -> None:
        self.mouse = FakeMouse()
        self.keyboard = FakeKeyboard()


class FakeLocator:
    def __init__(self) -> None:
        self.scroll_calls = 0
        self.hover_calls = 0
        self.focus_calls = 0

    async def scroll_into_view_if_needed(self) -> None:
        self.scroll_calls += 1

    async def hover(self) -> None:
        self.hover_calls += 1

    async def focus(self) -> None:
        self.focus_calls += 1

    async def bounding_box(self) -> dict[str, float]:
        return {"x": 100.0, "y": 50.0, "width": 120.0, "height": 40.0}


def test_human_click_locator_moves_then_clicks() -> None:
    page = FakePage()
    locator = FakeLocator()

    asyncio.run(human_click_locator(page=page, locator=locator))

    assert locator.scroll_calls == 1
    assert locator.hover_calls == 1
    assert len(page.mouse.moves) >= 2
    assert len(page.mouse.clicks) == 1


def test_human_type_locator_focuses_selects_and_types_with_delay() -> None:
    page = FakePage()
    locator = FakeLocator()

    asyncio.run(human_type_locator(page=page, locator=locator, text="hello"))

    assert locator.scroll_calls == 1
    assert locator.focus_calls == 1
    assert page.keyboard.presses == ["Control+A"]
    assert page.keyboard.typed == [("hello", 90)]
