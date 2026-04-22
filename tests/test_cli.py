from __future__ import annotations

from click.testing import CliRunner

from macrobania.cli import main


def test_version() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "macrobania" in result.output.lower()


def test_help() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    for cmd in ("record", "inspect", "semanticize", "play", "info", "doctor"):
        assert cmd in result.output


def test_record_help() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["record", "--help"])
    assert result.exit_code == 0
    assert "--task-name" in result.output
    assert "--duration" in result.output


def test_record_requires_task_name() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["record"])
    assert result.exit_code != 0
    assert "task-name" in result.output.lower() or "missing option" in result.output.lower()


def test_inspect_list_empty_ok(tmp_settings, monkeypatch) -> None:
    monkeypatch.setenv("MACROBANIA_DATA_DIR", str(tmp_settings.data_dir))
    from macrobania.config import reset_settings
    from macrobania.storage.db import reset_db_singleton

    reset_settings()
    reset_db_singleton()
    runner = CliRunner()
    result = runner.invoke(main, ["inspect", "--list"])
    assert result.exit_code == 0


def test_info_prints_table() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["info"])
    assert result.exit_code == 0
    assert "data_dir" in result.output
    assert "vlm.grounder_model" in result.output
