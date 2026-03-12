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

PASSWORD_ENV_VAR = "OPENAI_ACCOUNT_PASSWORD"

__all__ = [
    "GRAPH_API_BASE",
    "GraphApiProvider",
    "MAIL_POLL_INTERVAL_SECONDS",
    "PASSWORD_ENV_VAR",
    "WYX66_API_BASE",
    "Wyx66Provider",
    "create_mail_provider",
    "extract_verification_code",
]
