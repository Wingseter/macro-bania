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


def test_record_stub_errors() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["record", "--task-name", "x"])
    assert result.exit_code != 0
    assert "Phase 1" in result.output or "미구현" in result.output


def test_info_prints_table() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["info"])
    assert result.exit_code == 0
    assert "data_dir" in result.output
    assert "vlm.grounder_model" in result.output
