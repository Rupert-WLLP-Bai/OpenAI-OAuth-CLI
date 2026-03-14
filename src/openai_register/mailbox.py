from __future__ import annotations

from openai_auth_core.mailbox import (
    GRAPH_API_BASE,
    GraphApiProvider,
    MAIL_POLL_INTERVAL_SECONDS,
    WYX66_API_BASE,
    Wyx66Provider,
    create_mail_provider,
    extract_verification_code,
)


DEFAULT_PASSWORD = "C.WLLP159357"

__all__ = [
    "DEFAULT_PASSWORD",
    "GRAPH_API_BASE",
    "GraphApiProvider",
    "MAIL_POLL_INTERVAL_SECONDS",
    "WYX66_API_BASE",
    "Wyx66Provider",
    "create_mail_provider",
    "extract_verification_code",
]
