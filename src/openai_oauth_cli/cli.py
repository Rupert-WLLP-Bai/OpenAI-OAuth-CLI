from __future__ import annotations

import asyncio
import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys
import webbrowser

from dotenv import load_dotenv

from .accounts_db import AccountStore
from .admin_server import LocalAccountAdminServer
from .browser import PatchrightBrowser
from .callback import CallbackServer
from .mailbox import DEFAULT_ACCOUNTS_FILE, Wyx66Provider
from .oauth import (
    build_auth_url,
    build_callback_url,
    exchange_code_for_tokens,
    make_pkce_material,
    parse_callback_url,
)
from .state_machine import LoginStateMachine

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "accounts.sqlite3"
PASSWORD_ENV_VAR = "OPENAI_ACCOUNT_PASSWORD"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OpenAI OAuth CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    login = subparsers.add_parser("login", help="Automate login and print a refresh token")
    login.add_argument("--email", required=True, help="OpenAI account email address")
    login.add_argument("--password", help=f"OpenAI account password. Defaults to ${PASSWORD_ENV_VAR} from .env when omitted.")
    login.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="Path to the SQLite database")
    login.add_argument(
        "--accounts-file",
        default=str(DEFAULT_ACCOUNTS_FILE),
        help="Deprecated and ignored. Login account lookups now come from --db-path.",
    )
    login.add_argument("--callback-port", type=int, default=1455)
    login.add_argument("--timeout", type=int, default=300)
    login.add_argument("--proxy")

    db = subparsers.add_parser("db", help="Manage the account SQLite database")
    db_subparsers = db.add_subparsers(dest="db_command", required=True)

    db_init = db_subparsers.add_parser("init", help="Initialize the account SQLite database")
    db_init.add_argument("--db-path", required=True, help="Path to the SQLite database")

    db_import_txt = db_subparsers.add_parser("import-txt", help="Sync mailbox metadata from one or more text exports")
    db_import_txt.add_argument("--db-path", required=True, help="Path to the SQLite database")
    db_import_txt.add_argument(
        "--txt-path",
        action="append",
        required=True,
        help="Path to a text export file. Repeat to sync multiple files in order.",
    )

    db_serve = db_subparsers.add_parser("serve", help="Run the localhost account admin server")
    db_serve.add_argument("--db-path", required=True, help="Path to the SQLite database")
    db_serve.add_argument("--port", type=int, default=0, help="Port for the localhost admin server")
    db_serve.add_argument("--proxy")
    db_serve.add_argument("--no-open-browser", action="store_true")

    db_summary = db_subparsers.add_parser("summary", help="Print account totals grouped by group name")
    db_summary.add_argument("--db-path", required=True, help="Path to the SQLite database")

    return parser


def stderr_log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def resolve_proxy(proxy: str | None) -> str | None:
    if proxy:
        return proxy
    for env_var in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        value = os.getenv(env_var)
        if value:
            return value.strip()
    return None


def resolve_password(password: str | None) -> str:
    if password and password.strip():
        return password
    load_dotenv(dotenv_path=Path.cwd() / ".env")
    env_password = os.getenv(PASSWORD_ENV_VAR, "").strip()
    if env_password:
        return env_password
    raise RuntimeError(f"account password is required. Pass --password or set {PASSWORD_ENV_VAR}.")


def _missing_login_db_message(db_path: Path) -> str:
    db_path_str = str(db_path)
    return (
        f"login database is missing or uninitialized at {db_path_str}. "
        f"Run `openai-oauth-cli db init --db-path {db_path_str}` "
        f"and `openai-oauth-cli db import-txt --db-path {db_path_str} --txt-path <accounts.txt>`."
    )


def _empty_login_db_message(db_path: Path) -> str:
    return (
        f"login database has no imported accounts at {db_path}. "
        f"Run `openai-oauth-cli db import-txt --db-path {db_path} --txt-path <accounts.txt>`."
    )


def _missing_db_init_message(db_path: Path) -> str:
    return (
        f"account database is missing or uninitialized at {db_path}. "
        f"Run `openai-oauth-cli db init --db-path {db_path}` first."
    )


def _is_missing_table_error(exc: sqlite3.OperationalError) -> bool:
    return str(exc).strip().casefold().startswith("no such table: ")


async def run_login(
    *,
    email: str,
    password: str,
    accounts_file: str | None,
    db_path: str | None = None,
    callback_port: int,
    timeout: int,
    proxy: str | None,
) -> str:
    del accounts_file
    resolved_db_path = Path(db_path or DEFAULT_DB_PATH)
    store = AccountStore(resolved_db_path)
    if not store.table_exists("accounts"):
        raise RuntimeError(_missing_login_db_message(resolved_db_path))
    try:
        with sqlite3.connect(resolved_db_path) as connection:
            total_row = connection.execute("SELECT COUNT(*) FROM accounts").fetchone()
        assert total_row is not None
        if int(total_row[0]) == 0:
            raise RuntimeError(_empty_login_db_message(resolved_db_path))
        account = store.find_account_by_email(email)
    except sqlite3.OperationalError as exc:
        if _is_missing_table_error(exc):
            raise RuntimeError(_missing_login_db_message(resolved_db_path)) from exc
        raise
    proxy = resolve_proxy(proxy)
    code_verifier, code_challenge, state = make_pkce_material()
    server = CallbackServer(port=callback_port)

    await server.start()
    callback_task = asyncio.create_task(server.wait_for_result(timeout=timeout))
    try:
        auth_url = build_auth_url(
            callback_port=callback_port,
            code_challenge=code_challenge,
            state=state,
        )
        code_provider = Wyx66Provider(proxy=proxy)
        await code_provider.prime_inbox(account=account)
        async with PatchrightBrowser(
            proxy=proxy,
            callback_port=callback_port,
            callback_task=callback_task,
        ) as browser:
            machine = LoginStateMachine(browser=browser, code_provider=code_provider)
            await browser.open_authorization_page(auth_url)
            await machine.complete_login(
                account=account,
                email=email,
                password=password,
                timeout=timeout,
            )

        result = await callback_task
        if result.error:
            raise RuntimeError(f"oauth error: {result.error} {result.error_description}".strip())

        code = parse_callback_url(
            f"{build_callback_url(callback_port)}?code={result.code}&state={result.state}",
            expected_state=state,
        )
        bundle = await exchange_code_for_tokens(
            code=code,
            code_verifier=code_verifier,
            redirect_uri=build_callback_url(callback_port),
            proxy=proxy,
        )
        return bundle.refresh_token
    finally:
        if not callback_task.done():
            callback_task.cancel()
        await server.stop()


def run_db_command(args: argparse.Namespace) -> int:
    db_path = Path(args.db_path)
    store = AccountStore(db_path)
    if args.db_command == "init":
        store.init_db()
        sys.stdout.write("status=ok\n")
        return 0

    if args.db_command == "serve":
        if not store.tables_exist("accounts", "source_files", "account_sources"):
            raise RuntimeError(_missing_db_init_message(db_path))

        async def serve() -> int:
            server = LocalAccountAdminServer(
                db_path=db_path,
                port=args.port,
                proxy=args.proxy,
            )
            await server.start()
            admin_url = f"{server.base_url}/"
            sys.stdout.write(f"admin_url={admin_url}\n")
            if not args.no_open_browser:
                webbrowser.open(admin_url)
            try:
                await server.wait_until_cancelled()
            except asyncio.CancelledError:
                pass
            finally:
                await server.stop()
            return 0

        return asyncio.run(serve())

    if args.db_command == "import-txt":
        if not store.tables_exist("accounts", "source_files", "account_sources"):
            raise RuntimeError(_missing_db_init_message(db_path))
        try:
            stats = store.import_txt_files(Path(path) for path in args.txt_path)
        except sqlite3.OperationalError as exc:
            if _is_missing_table_error(exc):
                raise RuntimeError(_missing_db_init_message(db_path)) from exc
            raise
        sys.stdout.write(f"status=ok imported={stats.imported} skipped={stats.skipped}\n")
        return 0

    if args.db_command == "summary":
        if not store.table_exists("accounts"):
            raise RuntimeError(_missing_db_init_message(db_path))
        try:
            with sqlite3.connect(args.db_path) as connection:
                connection.row_factory = sqlite3.Row
                total_row = connection.execute("SELECT COUNT(*) AS count FROM accounts").fetchone()
                assert total_row is not None
                group_rows = connection.execute(
                    """
                    SELECT group_name, COUNT(*) AS count
                    FROM accounts
                    GROUP BY group_name
                    ORDER BY lower(group_name), group_name
                    """
                ).fetchall()
        except sqlite3.OperationalError as exc:
            if _is_missing_table_error(exc):
                raise RuntimeError(_missing_db_init_message(db_path)) from exc
            raise

        payload = {
            "accounts": int(total_row["count"]),
            "groups": {str(row["group_name"]): int(row["count"]) for row in group_rows},
        }
        sys.stdout.write(json.dumps(payload, separators=(",", ":")) + "\n")
        return 0

    raise ValueError(f"unsupported db command: {args.db_command}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "db":
        try:
            return run_db_command(args)
        except BrokenPipeError:
            raise
        except KeyboardInterrupt:
            stderr_log("DB command interrupted")
            return 130
        except Exception as exc:
            stderr_log(str(exc))
            return 1

    try:
        password = resolve_password(args.password)
        refresh_token = asyncio.run(
            run_login(
                email=args.email,
                password=password,
                accounts_file=args.accounts_file,
                db_path=args.db_path,
                callback_port=args.callback_port,
                timeout=args.timeout,
                proxy=args.proxy,
            )
        )
    except KeyboardInterrupt:
        stderr_log("Login interrupted")
        return 130
    except Exception as exc:
        stderr_log(str(exc))
        return 1

    if args.command == "login":
        sys.stdout.write(f"{refresh_token}\n")
        return 0

    return 2
