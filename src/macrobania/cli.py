"""macro-bania CLI.

4개 주 명령 스텁. 실제 로직은 Phase 1부터 채운다.
"""
from __future__ import annotations

import click

from macrobania import __version__


@click.group(help="macro-bania — Context-aware macro via VLM.")
@click.version_option(__version__, prog_name="macrobania")
def main() -> None:
    pass


@main.command(help="데스크톱 행동을 녹화한다. (Phase 1)")
@click.option("--task-name", required=True, help="녹화 이름")
@click.option("--description", default="", help="태스크 설명")
@click.option("--output-dir", default=None, help="저장 경로 (기본 %APPDATA%/macrobania)")
def record(task_name: str, description: str, output_dir: str | None) -> None:
    click.echo(f"[stub] record: task={task_name!r}")
    raise click.ClickException("Phase 1 미구현 — src/macrobania/recording/ 를 만들어야 함")


@main.command(help="녹화를 검사한다. (Phase 1)")
@click.argument("recording_id")
def inspect(recording_id: str) -> None:
    click.echo(f"[stub] inspect: {recording_id}")
    raise click.ClickException("Phase 1 미구현")


@main.command(help="녹화를 의미 단위(Step)로 변환한다. (Phase 2)")
@click.argument("recording_id")
@click.option("--model", default="qwen3.5:0.8b", help="Captioner 모델 이름")
def semanticize(recording_id: str, model: str) -> None:
    click.echo(f"[stub] semanticize: {recording_id} with {model}")
    raise click.ClickException("Phase 2 미구현")


@main.command(help="녹화를 재생한다. (Phase 3+)")
@click.argument("recording_id")
@click.option(
    "--mode",
    type=click.Choice(["a", "b", "c"], case_sensitive=False),
    default="b",
    help="a=Faithful, b=Grounded(기본), c=Autonomous",
)
@click.option("--dry-run/--execute", default=True, help="기본은 dry-run (실제 입력 주입 X)")
@click.option("--speed", default=1.0, type=float, help="재생 속도 배율 (0.25~2.0)")
def play(recording_id: str, mode: str, dry_run: bool, speed: float) -> None:
    click.echo(
        f"[stub] play: {recording_id} mode={mode} dry_run={dry_run} speed={speed}"
    )
    raise click.ClickException("Phase 3+ 미구현")


if __name__ == "__main__":
    main()
