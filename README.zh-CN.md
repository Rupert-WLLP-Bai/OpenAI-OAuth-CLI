# OpenAI OAuth CLI 中文说明

[English README](README.md)

这个项目提供两组 Python CLI：

- 自动化 OpenAI 网页登录流程，并输出 `refresh_token`
- 自动化 ChatGPT 账号注册，并把本地 SQLite 账号状态写回数据库

## 仓库现状

这个仓库现在有两条线：

- 本地私有开发线：日常开发、调试、实验都在这个仓库里完成
- 公开镜像线：发布到 GitHub 的版本必须先做脱敏，再单独发布

如果你只是本地开发，请直接使用当前仓库。
如果你准备更新公开 GitHub 仓库，请先看 [`AGENTS.md`](AGENTS.md) 和 [`CLAUDE.md`](CLAUDE.md) 里的 `Private/Public Workflow` 部分。

## 项目结构

- `src/openai_oauth_cli/`：登录 CLI、SQLite 账号库、OAuth 回调处理、登录状态机
- `src/openai_register/`：注册 CLI、诊断日志、注册状态机、登录验证
- `src/openai_auth_core/`：两条流程共用的浏览器、邮箱、回调、OAuth 辅助代码
- `tests/`：单元测试和集成测试
- `tests/e2e/`：受环境变量控制的 live E2E
- `docs/plans/`：设计和实现计划

## 常用命令

安装开发依赖：

```bash
uv sync --group dev
```

运行测试：

```bash
uv run pytest
uv run ruff check .
uv run ty check
```

初始化和导入账号库：

```bash
uv run openai-oauth-cli db init --db-path data/accounts.sqlite3
uv run openai-oauth-cli db import-txt \
  --db-path data/accounts.sqlite3 \
  --txt-path secrets/example_accounts.txt
uv run openai-oauth-cli db summary --db-path data/accounts.sqlite3
```

运行登录：

```bash
uv run openai-oauth-cli login --email you@example.com --db-path data/accounts.sqlite3
```

运行注册：

```bash
uv run openai-register register --email you@example.com --db-path data/accounts.sqlite3
uv run openai-register verify-login --email you@example.com --db-path data/accounts.sqlite3
```

## 密码配置

如果你不想每次都传 `--password`，先在本地创建 `.env`：

```bash
cp .env.example .env
```

然后设置：

```bash
OPENAI_ACCOUNT_PASSWORD=your-password-here
```

命令行里显式传入 `--password` 时，会优先使用命令行参数。

## Live E2E

Live E2E 默认跳过，只有在显式设置环境变量后才会运行：

```bash
OPENAI_LIVE_E2E=1 \
OPENAI_E2E_DB_PATH=/absolute/path/to/accounts.sqlite3 \
uv run pytest tests/e2e/test_live_flows.py -m live_e2e -v
```

## 安全说明

- 不要提交 `.env`
- 不要提交 `data/`、`secrets/`、`logs/`、SQLite 数据库、token、代理配置
- 不要把本地私有历史直接 push 到公开 GitHub
- 公开版本必须先做脱敏，再单独发布
