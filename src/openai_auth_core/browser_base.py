from __future__ import annotations

from typing import Any, cast


CHROMIUM_ARGS = (
    "--disable-blink-features=AutomationControlled",
    "--disable-web-security",
    "--disable-features=IsolateOrigins,site-per-process",
)
DEFAULT_VIEWPORT = {"width": 1280, "height": 800}
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


async def start_browser_session(*, proxy: str | None) -> tuple[Any, Any, Any, Any]:
    from patchright.async_api import async_playwright

    playwright = await async_playwright().start()
    browser_args: dict[str, Any] = {
        "headless": False,
        "args": list(CHROMIUM_ARGS),
    }
    if proxy:
        browser_args["proxy"] = {"server": proxy}

    browser = await playwright.chromium.launch(**browser_args)
    context = await browser.new_context(
        viewport=cast(Any, DEFAULT_VIEWPORT),
        user_agent=DEFAULT_USER_AGENT,
    )
    page = await context.new_page()
    return playwright, browser, context, page


async def stop_browser_session(*, playwright: Any, browser: Any, context: Any) -> None:
    if context is not None:
        await context.close()
    if browser is not None:
        await browser.close()
    if playwright is not None:
        await playwright.stop()
