from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
import sys

from dotenv import load_dotenv

from .accounts_db import RegistrationAccountStore
from .browser import PatchrightBrowser
from .callback import CallbackServer
from .diagnostics import RunLogger
from .mailbox import Wyx66Provider
from .models import MailAccountRecord
from .oauth import build_auth_url, make_pkce_material, validate_callback_result
from .state_machine import OAuthLoginVerifier, RegistrationStateMachine


DEFAULT_CALLBACK_PORT = 1455
DEFAULT_ARTIFACTS_DIR = Path("logs/openai-register")
PASSWORD_ENV_VAR = "OPENAI_ACCOUNT_PASSWORD"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OpenAI account registration CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    register = subparsers.add_parser("register", help="Automate ChatGPT account registration")
    register.add_argument("--email", required=True, help="Account email address")
    register.add_argument("--db-path", required=True, help="SQLite account database path")
    register.add_argument("--password", help=f"Account password. Defaults to ${PASSWORD_ENV_VAR} from .env when omitted.")
    register.add_argument("--timeout", type=int, default=300)
    register.add_argument("--proxy")
    register.add_argument("--callback-port", type=int, default=DEFAULT_CALLBACK_PORT)
    register.add_argument("--artifacts-dir", default=str(DEFAULT_ARTIFACTS_DIR))

    verify = subparsers.add_parser("verify-login", help="Verify that an account can complete a real login flow")
    verify.add_argument("--email", required=True, help="Account email address")
    verify.add_argument("--db-path", required=True, help="SQLite account database path")
    verify.add_argument("--password", help=f"Account password. Defaults to ${PASSWORD_ENV_VAR} from .env when omitted.")
    verify.add_argument("--timeout", type=int, default=300)
    verify.add_argument("--proxy")
    verify.add_argument("--callback-port", type=int, default=DEFAULT_CALLBACK_PORT)
    verify.add_argument("--artifacts-dir", default=str(DEFAULT_ARTIFACTS_DIR))

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


async def run_register(
    *,
    email: str,
    password: str,
    db_path: str,
    timeout: int,
    proxy: str | None,
    callback_port: int,
    artifacts_dir: str,
) -> str:
    logger = RunLogger(base_dir=Path(artifacts_dir), command_name="register", email=email)
    store = RegistrationAccountStore(Path(db_path))
    proxy = resolve_proxy(proxy)
    account = store.get_mail_account(email)
    logger.log_event("register_started", email=email, db_path=db_path)
    store.mark_registration_started(email)
    browser: PatchrightBrowser | None = None
    try:
        code_provider = Wyx66Provider(proxy=proxy)
        await code_provider.prime_inbox(account=account)
        async with PatchrightBrowser(proxy=proxy, logger=logger) as browser:
            machine = RegistrationStateMachine(browser=browser, code_provider=code_provider)
            await browser.open_chatgpt()
            await machine.complete_registration(
                account=account,
                email=email,
                password=password,
                timeout=timeout,
            )
        await verify_registered_account(
            account=account,
            email=email,
            password=password,
            timeout=timeout,
            proxy=proxy,
            callback_port=callback_port,
            logger=logger,
        )
        store.mark_registration_succeeded(email)
    except Exception as exc:
        if browser is not None:
            await browser.capture_debug_artifacts("register-failure")
        logger.log_event("register_failed", error=str(exc))
        failure_message = str(exc)
        try:
            store.mark_registration_failed(email, failure_message)
        except Exception:
            pass
        raise RuntimeError(f"{failure_message} (log_dir={logger.run_dir})") from exc
    logger.log_event("register_succeeded", email=email)
    return email


async def verify_registered_account(
    *,
    account: MailAccountRecord,
    email: str,
    password: str,
    timeout: int,
    proxy: str | None,
    callback_port: int,
    logger: RunLogger,
) -> None:
    logger.log_event("strict_verification_started", email=email, callback_port=callback_port)
    _, code_challenge, state = make_pkce_material()
    auth_url = build_auth_url(callback_port=callback_port, code_challenge=code_challenge, state=state)

    server = CallbackServer(port=callback_port)
    await server.start()
    callback_task = asyncio.create_task(server.wait_for_result(timeout=timeout))
    browser: PatchrightBrowser | None = None
    try:
        code_provider = Wyx66Provider(proxy=proxy)
        await code_provider.prime_inbox(account=account)
        async with PatchrightBrowser(proxy=proxy, logger=logger) as browser:
            verifier = OAuthLoginVerifier(browser=browser, code_provider=code_provider, logger=logger)
            await browser.open_authorization_page(auth_url)
            await verifier.complete_login(
                account=account,
                email=email,
                password=password,
                timeout=timeout,
                callback_url=server.callback_url,
                callback_task=callback_task,
            )
        result = await callback_task
        validate_callback_result(
            code=result.code,
            state=result.state,
            expected_state=state,
            error=result.error,
            error_description=result.error_description,
        )
        logger.log_event("strict_verification_succeeded", email=email)
    except Exception:
        if browser is not None:
            await browser.capture_debug_artifacts("verify-login-failure")
        raise
    finally:
        if not callback_task.done():
            callback_task.cancel()
        await server.stop()


async def run_verify_login(
    *,
    email: str,
    password: str,
    db_path: str,
    timeout: int,
    proxy: str | None,
    callback_port: int,
    artifacts_dir: str,
) -> str:
    logger = RunLogger(base_dir=Path(artifacts_dir), command_name="verify-login", email=email)
    store = RegistrationAccountStore(Path(db_path))
    proxy = resolve_proxy(proxy)
    account = store.get_mail_account(email)
    try:
        await verify_registered_account(
            account=account,
            email=email,
            password=password,
            timeout=timeout,
            proxy=proxy,
            callback_port=callback_port,
            logger=logger,
        )
    except Exception as exc:
        logger.log_event("verify_login_failed", error=str(exc))
        raise RuntimeError(f"{exc} (log_dir={logger.run_dir})") from exc
    logger.log_event("verify_login_succeeded", email=email)
    return email


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        if args.command == "register":
            password = resolve_password(args.password)
            email = asyncio.run(
                run_register(
                    email=args.email,
                    password=password,
                    db_path=args.db_path,
                    timeout=args.timeout,
                    proxy=args.proxy,
                    callback_port=args.callback_port,
                    artifacts_dir=args.artifacts_dir,
                )
            )
            sys.stdout.write(f"registered:{email}\n")
            return 0

        if args.command == "verify-login":
            password = resolve_password(args.password)
            email = asyncio.run(
                run_verify_login(
                    email=args.email,
                    password=password,
                    db_path=args.db_path,
                    timeout=args.timeout,
                    proxy=args.proxy,
                    callback_port=args.callback_port,
                    artifacts_dir=args.artifacts_dir,
                )
            )
            sys.stdout.write(f"verified:{email}\n")
            return 0
    except KeyboardInterrupt:
        stderr_log("Registration interrupted")
        return 130
    except Exception as exc:
        stderr_log(str(exc))
        return 1

    return 2
