#!/usr/bin/env python3
"""
批量登录辅助脚本

用法:
  # 方式1: 命令行传入邮箱列表
  uv run python scripts/batch_login.py --emails a@test.com b@test.com c@test.com --password 密码

  # 方式2: 从文件读取邮箱 (每行一个)
  uv run python scripts/batch_login.py --emails-file emails.txt --password 密码
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# 将 src 目录加入路径
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openai_oauth_cli.cli import run_login

DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "accounts.sqlite3"


async def batch_login(
    emails: list[str],
    password: str,
    db_path: str,
    start_port: int = 1455,
    save_to_db: bool = False,
) -> dict[str, str]:
    """批量登录并返回 email -> refresh_token 的映射"""
    results = {}

    for i, email in enumerate(emails):
        port = start_port + i
        print(f"[{i+1}/{len(emails)}] 登录 {email} (端口 {port})...", file=sys.stderr)

        try:
            token = await run_login(
                email=email,
                password=password,
                accounts_file=None,
                db_path=db_path,
                callback_port=port,
                timeout=300,
                proxy=None,
            )
            results[email] = token
            print(f"  -> 成功: {token[:20]}...", file=sys.stderr)
        except Exception as e:
            print(f"  -> 失败: {e}", file=sys.stderr)
            results[email] = None

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="批量登录 OpenAI 账号")
    parser.add_argument("--emails", nargs="+", help="邮箱列表")
    parser.add_argument("--emails-file", help="邮箱列表文件 (每行一个)")
    parser.add_argument("--password", required=True, help="统一密码")
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_DB_PATH),
        help=f"SQLite数据库路径 (默认: {DEFAULT_DB_PATH})",
    )
    parser.add_argument("--start-port", type=int, default=1455, help="起始端口")
    parser.add_argument(
        "--save-to-db",
        action="store_true",
        help="是否保存 refresh_token 回数据库 (未实现)",
    )

    args = parser.parse_args()

    # 收集邮箱
    emails = []
    if args.emails:
        emails.extend(args.emails)
    if args.emails_file:
        path = Path(args.emails_file)
        if path.exists():
            emails.extend(line.strip() for line in path.read_text().splitlines() if line.strip())

    if not emails:
        print("错误: 请提供 --emails 或 --emails-file", file=sys.stderr)
        return 1

    # 执行批量登录
    results = asyncio.run(
        batch_login(
            emails=emails,
            password=args.password,
            db_path=args.db_path,
            start_port=args.start_port,
            save_to_db=args.save_to_db,
        )
    )

    # 输出结果: stdout 只保留成功的 email:token 记录
    for email, token in results.items():
        if token:
            print(f"{email}:{token}")
        else:
            print(f"{email}:FAILED", file=sys.stderr)

    # 统计
    success = sum(1 for t in results.values() if t)
    print(f"\n成功: {success}/{len(emails)}", file=sys.stderr)

    return 0 if success == len(emails) else 1


if __name__ == "__main__":
    sys.exit(main())
