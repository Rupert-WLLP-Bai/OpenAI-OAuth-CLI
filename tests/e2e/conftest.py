from __future__ import annotations

import os
from pathlib import Path

import pytest


LIVE_E2E_ENV_VAR = "OPENAI_LIVE_E2E"
LIVE_E2E_DB_PATH_ENV_VAR = "OPENAI_E2E_DB_PATH"


def require_live_e2e_db_path() -> Path:
    if os.getenv(LIVE_E2E_ENV_VAR) != "1":
        pytest.skip(f"set {LIVE_E2E_ENV_VAR}=1 to run live end-to-end tests")

    raw_db_path = os.getenv(LIVE_E2E_DB_PATH_ENV_VAR, "").strip()
    if not raw_db_path:
        pytest.skip(f"set {LIVE_E2E_DB_PATH_ENV_VAR} to an existing SQLite database path")

    db_path = Path(raw_db_path).expanduser()
    if not db_path.is_file():
        pytest.skip(f"{LIVE_E2E_DB_PATH_ENV_VAR} does not point to an existing file: {db_path}")

    return db_path


@pytest.fixture
def live_e2e_enabled() -> bool:
    require_live_e2e_db_path()
    return True


@pytest.fixture
def live_e2e_db_path(live_e2e_enabled: bool) -> Path:
    del live_e2e_enabled
    return require_live_e2e_db_path()
