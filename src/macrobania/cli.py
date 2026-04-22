"""macro-bania CLI.

구현된 명령:
  - ``info``         : 환경 정보 덤프
  - ``doctor``       : VLM 엔드포인트/데이터 디렉토리 연결 점검
  - ``record``       : (P1 스텁)
  - ``inspect``      : (P1 스텁)
  - ``semanticize``  : (P2 스텁)
  - ``play``         : (P3+ 스텁)
"""
from __future__ import annotations

import json
import platform
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from macrobania import __version__
from macrobania.agent.client import VLMClient
from macrobania.config import get_settings
from macrobania.logging import configure_logging
from macrobania.storage import get_db

_console = Console()


@click.group(help="macro-bania — Context-aware macro via VLM.")
@click.version_option(__version__, prog_name="macrobania")
@click.option(
    "--log-level",
    default=None,
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
)
def main(log_level: str | None) -> None:
    configure_logging(level=log_level)


# ---------------------------------------------------------------------------
# info / doctor
# ---------------------------------------------------------------------------


@main.command(help="환경 정보 출력")
def info() -> None:
    settings = get_settings()

    table = Table(title="macro-bania environment", show_lines=False)
    table.add_column("key", style="cyan")
    table.add_column("value")

    table.add_row("version", __version__)
    table.add_row("python", f"{sys.version.split()[0]} ({sys.executable})")
    table.add_row("platform", f"{platform.system()} {platform.release()} ({platform.machine()})")
    table.add_row("hardware_tier", settings.hardware_tier)
    table.add_row("data_dir", str(settings.data_dir))
    table.add_row("db_path", str(settings.db_path))
    table.add_row("vlm.base_url", str(settings.vlm.base_url))
    table.add_row("vlm.grounder_model", settings.vlm.grounder_model)
    table.add_row("vlm.captioner_model", settings.vlm.captioner_model)
    table.add_row("vlm.planner_model", settings.vlm.planner_model)
    table.add_row("safety.dry_run_default", str(settings.safety.dry_run_default))
    table.add_row("safety.pii_scrub", str(settings.safety.pii_scrub_enabled))
    table.add_row("safety.kill_switch", settings.safety.kill_switch_hotkey)

    _console.print(table)


@main.command(help="설치/연결 점검")
def doctor() -> None:
    settings = get_settings()
    settings.ensure_dirs()
    ok = True

    # 1. 데이터 디렉터리
    try:
        probe = settings.data_dir / ".probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        _console.print(f"[green][ OK ][/green] data_dir writable: {settings.data_dir}")
    except Exception as e:
        _console.print(f"[red][FAIL][/red] data_dir not writable: {e}")
        ok = False

    # 2. SQLite
    try:
        db = get_db(settings)
        conn = db.connect()
        v = conn.execute("PRAGMA user_version").fetchone()[0]
        _console.print(
            f"[green][ OK ][/green] sqlite schema v{v} at {settings.db_path}"
        )
    except Exception as e:
        _console.print(f"[red][FAIL][/red] sqlite: {e}")
        ok = False

    # 3. VLM 엔드포인트
    try:
        client = VLMClient.from_env()
        if client.ping():
            _console.print(
                f"[green][ OK ][/green] VLM endpoint reachable: {settings.vlm.base_url}"
            )
        else:
            _console.print(
                f"[yellow][WARN][/yellow] VLM endpoint NOT reachable: {settings.vlm.base_url}\n"
                "    - Ollama 기동:  ollama serve\n"
                f"    - 모델 pull:    ollama pull {settings.vlm.grounder_model}"
            )
            ok = False
    except Exception as e:
        _console.print(f"[red][FAIL][/red] VLM client: {e}")
        ok = False

    sys.exit(0 if ok else 1)


# ---------------------------------------------------------------------------
# P1+ 스텁
# ---------------------------------------------------------------------------


@main.command(help="데스크톱 행동을 녹화한다. (Phase 1)")
@click.option("--task-name", required=True)
@click.option("--description", default="")
@click.option("--output-dir", type=click.Path(path_type=Path), default=None)
def record(task_name: str, description: str, output_dir: Path | None) -> None:
    _ = description, output_dir
    _console.print(f"[yellow]stub[/yellow] record: task={task_name!r}")
    raise click.ClickException("Phase 1 미구현 — src/macrobania/recording/ 가 곧 추가됨")


@main.command(help="녹화를 검사한다. (Phase 1)")
@click.argument("recording_id")
@click.option("--format", "fmt", type=click.Choice(["json", "text"]), default="text")
def inspect(recording_id: str, fmt: str) -> None:
    _ = recording_id, fmt
    raise click.ClickException("Phase 1 미구현")


@main.command(help="녹화를 의미 단위(Step)로 변환한다. (Phase 2)")
@click.argument("recording_id")
@click.option("--model", default=None, help="Captioner 모델 override")
def semanticize(recording_id: str, model: str | None) -> None:
    _ = recording_id, model
    raise click.ClickException("Phase 2 미구현")


@main.command(help="녹화를 재생한다. (Phase 3+)")
@click.argument("recording_id")
@click.option("--mode", type=click.Choice(["a", "b", "c"], case_sensitive=False), default="b")
@click.option("--dry-run/--execute", default=True)
@click.option("--speed", default=1.0, type=float)
def play(recording_id: str, mode: str, dry_run: bool, speed: float) -> None:
    _ = recording_id, mode, dry_run, speed
    raise click.ClickException("Phase 3+ 미구현")


@main.command(help="현재 설정을 JSON으로 출력 (자동화용)")
def config_dump() -> None:
    settings = get_settings()
    data = settings.model_dump(mode="json")
    _console.print_json(json.dumps(data, default=str))


if __name__ == "__main__":
    main()
