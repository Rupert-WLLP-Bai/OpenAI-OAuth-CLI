from __future__ import annotations

from pathlib import Path

from unittest.mock import AsyncMock

import pytest

from openai_oauth_cli import cli


def test_db_import_txt_creates_accounts_and_summary(tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "accounts.sqlite3"
    txt_path = tmp_path / "accounts.txt"
    txt_path.write_text(
        "\n".join(
            [
                "a@example.com----pw----uuid-a----rt-a----x----default",
                "b@example.com----pw----uuid-b----rt-b----x----default",
                "c@example.com----pw----uuid-c----rt-c----x----gpt team 1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert cli.main(["db", "init", "--db-path", str(db_path)]) == 0
    _ = capsys.readouterr()

    assert cli.main(["db", "import-txt", "--db-path", str(db_path), "--txt-path", str(txt_path)]) == 0
    captured = capsys.readouterr()
    assert captured.out == "status=ok imported=3 skipped=0\n"
    assert captured.err == ""

    assert cli.main(["db", "summary", "--db-path", str(db_path)]) == 0

    captured = capsys.readouterr()
    assert captured.out == '{"accounts":3,"groups":{"default":2,"gpt team 1":1}}\n'
    assert captured.err == ""


def test_db_import_txt_accepts_multiple_txt_paths_and_preserves_sqlite_state(tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "accounts.sqlite3"
    first_path = tmp_path / "accounts-first.txt"
    second_path = tmp_path / "accounts-second.txt"
    first_path.write_text(
        "shared@example.com----pw----uuid-shared-1----rt-shared-1----x----default\n",
        encoding="utf-8",
    )
    second_path.write_text(
        "\n".join(
            [
                "shared@example.com----pw----uuid-shared-2----rt-shared-2----x----team 3",
                "new@example.com----pw----uuid-new----rt-new----x----default",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert cli.main(["db", "init", "--db-path", str(db_path)]) == 0
    _ = capsys.readouterr()

    assert cli.main(["db", "import-txt", "--db-path", str(db_path), "--txt-path", str(first_path)]) == 0
    _ = capsys.readouterr()

    import sqlite3

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "UPDATE accounts SET is_registered = 1, is_primary = 1 WHERE lower(email) = lower(?)",
            ("shared@example.com",),
        )
        connection.commit()

    assert (
        cli.main(
            [
                "db",
                "import-txt",
                "--db-path",
                str(db_path),
                "--txt-path",
                str(first_path),
                "--txt-path",
                str(second_path),
            ]
        )
        == 0
    )
    captured = capsys.readouterr()
    assert captured.out == "status=ok imported=3 skipped=0\n"
    assert captured.err == ""

    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT mail_client_id, mail_refresh_token, group_name, is_registered, is_primary
            FROM accounts
            WHERE lower(email) = lower(?)
            """,
            ("shared@example.com",),
        ).fetchone()
        new_row = connection.execute(
            """
            SELECT is_registered, is_primary
            FROM accounts
            WHERE lower(email) = lower(?)
            """,
            ("new@example.com",),
        ).fetchone()

    assert row == ("uuid-shared-2", "rt-shared-2", "default", 1, 1)
    assert new_row == (0, 0)


def test_db_import_txt_reports_skipped_rows(tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "accounts.sqlite3"
    txt_path = tmp_path / "accounts.txt"
    txt_path.write_text(
        "\n".join(
            [
                "a@example.com----pw----uuid-a----rt-a----x----default",
                "malformed-row",
                "missing-token@example.com----pw----uuid-b----  ----x----default",
                "b@example.com----pw----uuid-c----rt-c----x----default",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert cli.main(["db", "init", "--db-path", str(db_path)]) == 0
    _ = capsys.readouterr()

    assert cli.main(["db", "import-txt", "--db-path", str(db_path), "--txt-path", str(txt_path)]) == 0

    captured = capsys.readouterr()
    assert captured.out == "status=ok imported=2 skipped=2\n"
    assert captured.err == ""


def test_db_summary_reports_empty_database_exactly(tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "accounts.sqlite3"

    assert cli.main(["db", "init", "--db-path", str(db_path)]) == 0
    _ = capsys.readouterr()

    assert cli.main(["db", "summary", "--db-path", str(db_path)]) == 0

    captured = capsys.readouterr()
    assert captured.out == '{"accounts":0,"groups":{}}\n'
    assert captured.err == ""


@pytest.mark.parametrize("command", [["db", "import-txt"], ["db", "summary"]])
def test_db_commands_report_uninitialized_database_with_db_init_guidance(
    tmp_path: Path,
    capsys,
    command: list[str],
) -> None:
    db_path = tmp_path / "accounts.sqlite3"
    argv = [*command, "--db-path", str(db_path)]
    if command[-1] == "import-txt":
        txt_path = tmp_path / "accounts.txt"
        txt_path.write_text("a@example.com----pw----uuid-a----rt-a----x----default\n", encoding="utf-8")
        argv.extend(["--txt-path", str(txt_path)])

    assert cli.main(argv) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert (
        captured.err
        == (
            f"account database is missing or uninitialized at {db_path}. "
            f"Run `openai-oauth-cli db init --db-path {db_path}` first.\n"
        )
    )


def test_db_command_keyboard_interrupt_has_db_specific_message(
    tmp_path: Path,
    capsys,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "accounts.sqlite3"

    def raise_interrupt(_: object) -> int:
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "run_db_command", raise_interrupt)

    assert cli.main(["db", "summary", "--db-path", str(db_path)]) == 130

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "DB command interrupted\n"


def test_db_summary_does_not_catch_stdout_write_failures(
    tmp_path: Path,
    capsys,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "accounts.sqlite3"
    txt_path = tmp_path / "accounts.txt"
    txt_path.write_text(
        "a@example.com----pw----uuid-a----rt-a----x----default\n",
        encoding="utf-8",
    )

    assert cli.main(["db", "init", "--db-path", str(db_path)]) == 0
    _ = capsys.readouterr()

    assert cli.main(["db", "import-txt", "--db-path", str(db_path), "--txt-path", str(txt_path)]) == 0
    _ = capsys.readouterr()

    def fail_write(_: str) -> int:
        raise BrokenPipeError("broken pipe")

    monkeypatch.setattr(cli.sys.stdout, "write", fail_write)

    with pytest.raises(BrokenPipeError, match="broken pipe"):
        cli.main(["db", "summary", "--db-path", str(db_path)])


def test_login_does_not_catch_stdout_write_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "run_login", AsyncMock(return_value="rt_example"))

    def fail_write(_: str) -> int:
        raise BrokenPipeError("broken pipe")

    monkeypatch.setattr(cli.sys.stdout, "write", fail_write)

    with pytest.raises(BrokenPipeError, match="broken pipe"):
        cli.main(["login", "--email", "user@example.com"])


def test_db_serve_requires_initialized_database(tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "accounts.sqlite3"

    assert cli.main(["db", "serve", "--db-path", str(db_path), "--no-open-browser"]) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert (
        captured.err
        == (
            f"account database is missing or uninitialized at {db_path}. "
            f"Run `openai-oauth-cli db init --db-path {db_path}` first.\n"
        )
    )


def test_db_serve_starts_local_admin_server(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "accounts.sqlite3"
    txt_path = tmp_path / "accounts.txt"
    txt_path.write_text(
        "user@example.com----pw----uuid-user----rt-user----x----default\n",
        encoding="utf-8",
    )

    assert cli.main(["db", "init", "--db-path", str(db_path)]) == 0
    _ = capsys.readouterr()
    assert cli.main(["db", "import-txt", "--db-path", str(db_path), "--txt-path", str(txt_path)]) == 0
    _ = capsys.readouterr()

    events: list[tuple[str, object]] = []

    class FakeServer:
        def __init__(self, *, db_path: Path, port: int, proxy: str | None = None) -> None:
            events.append(("init", (db_path, port, proxy)))
            self.base_url = "http://localhost:4321"

        async def start(self) -> None:
            events.append(("start", None))

        async def wait_until_cancelled(self) -> None:
            events.append(("wait_until_cancelled", None))

        async def stop(self) -> None:
            events.append(("stop", None))

    monkeypatch.setattr(cli, "LocalAccountAdminServer", FakeServer)

    opened_urls: list[str] = []

    def fake_open(url: str) -> bool:
        opened_urls.append(url)
        return True

    monkeypatch.setattr(cli.webbrowser, "open", fake_open)

    assert cli.main(["db", "serve", "--db-path", str(db_path), "--port", "4321"]) == 0

    captured = capsys.readouterr()
    assert captured.err == ""
    assert "http://localhost:4321/" in captured.out
    assert events == [
        ("init", (db_path, 4321, None)),
        ("start", None),
        ("wait_until_cancelled", None),
        ("stop", None),
    ]
    assert opened_urls == ["http://localhost:4321/"]


def test_db_serve_respects_no_open_browser(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "accounts.sqlite3"
    txt_path = tmp_path / "accounts.txt"
    txt_path.write_text(
        "user@example.com----pw----uuid-user----rt-user----x----default\n",
        encoding="utf-8",
    )

    assert cli.main(["db", "init", "--db-path", str(db_path)]) == 0
    _ = capsys.readouterr()
    assert cli.main(["db", "import-txt", "--db-path", str(db_path), "--txt-path", str(txt_path)]) == 0
    _ = capsys.readouterr()

    class FakeServer:
        def __init__(self, *, db_path: Path, port: int, proxy: str | None = None) -> None:
            self.base_url = "http://localhost:9999"

        async def start(self) -> None:
            return None

        async def wait_until_cancelled(self) -> None:
            return None

        async def stop(self) -> None:
            return None

    monkeypatch.setattr(cli, "LocalAccountAdminServer", FakeServer)

    def fail_open(url: str) -> bool:
        raise AssertionError(f"webbrowser.open should not be called: {url}")

    monkeypatch.setattr(cli.webbrowser, "open", fail_open)

    assert cli.main(["db", "serve", "--db-path", str(db_path), "--no-open-browser"]) == 0
    captured = capsys.readouterr()
    assert "http://localhost:9999/" in captured.out
