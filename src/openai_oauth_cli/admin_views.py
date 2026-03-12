from __future__ import annotations

from .admin_shell_css import ADMIN_SHELL_CSS
from .admin_shell_html import ADMIN_SHELL_BODY
from .admin_shell_js import ADMIN_SHELL_JS


def render_admin_shell() -> str:
    return (
        "<!doctype html>\n"
        "<html lang=\"zh-CN\">\n"
        "  <head>\n"
        "    <meta charset=\"utf-8\">\n"
        "    <title>账号管理系统</title>\n"
        "    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "    <style>\n"
        f"{ADMIN_SHELL_CSS}\n"
        "    </style>\n"
        "  </head>\n"
        "  <body>\n"
        f"{ADMIN_SHELL_BODY}\n"
        "    <script>\n"
        f"{ADMIN_SHELL_JS}\n"
        "    </script>\n"
        "  </body>\n"
        "</html>\n"
    )
