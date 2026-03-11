from pathlib import Path


def test_project_files_exist() -> None:
    assert Path("src/openai_oauth_cli/cli.py").exists()
    assert Path("pyproject.toml").exists()
