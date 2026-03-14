from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


ACCOUNT_PASSWORD_ENV_VAR = "OPENAI_ACCOUNT_PASSWORD"


def load_runtime_dotenv() -> None:
    dotenv_path = Path.cwd() / ".env"
    if dotenv_path.is_file():
        load_dotenv(dotenv_path, override=False)


def resolve_account_password(explicit_password: str | None) -> str:
    if explicit_password:
        return explicit_password

    load_runtime_dotenv()
    env_password = os.getenv(ACCOUNT_PASSWORD_ENV_VAR, "").strip()
    if env_password:
        return env_password

    raise RuntimeError(
        "account password is required. "
        f"Pass `--password` or set `{ACCOUNT_PASSWORD_ENV_VAR}` in `.env` or the environment."
    )
