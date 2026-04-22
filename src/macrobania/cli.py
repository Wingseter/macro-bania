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
from macrobania.recording import RecordingRepo, RecordingSession
from macrobania.recording.session import RecorderConfig
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


@main.command(help="데스크톱 행동을 녹화한다. Ctrl+C 로 종료.")
@click.option("--task-name", required=True, help="녹화 이름")
@click.option("--description", default="", help="태스크 설명")
@click.option(
    "--target-process",
    default=None,
    help="대상 프로세스 이름 (예: chrome.exe). 재생 시 화이트리스트로 사용",
)
@click.option("--fps", default=6, type=click.IntRange(1, 30))
@click.option("--duration", default=None, type=float, help="자동 종료까지 초 (미지정 시 Ctrl+C)")
def record(
    task_name: str,
    description: str,
    target_process: str | None,
    fps: int,
    duration: float | None,
) -> None:
    import signal
    import threading

    session = RecordingSession(
        task_name=task_name,
        description=description,
        target_process=target_process,
        cfg=RecorderConfig(capture_fps=fps),
    )

    def _sig(_signum: int, _frame: object) -> None:
        _console.print("\n[yellow]stopping...[/yellow]")
        session.stop()

    signal.signal(signal.SIGINT, _sig)
    if duration is not None:
        threading.Timer(duration, session.stop).start()

    _console.print(
        f"[green]recording[/green] task={task_name!r} fps={fps}"
        + (f" duration={duration}s" if duration else " (Ctrl+C to stop)")
    )
    rec = session.run()
    _console.print(
        f"[green]done[/green] id={rec.id} frames={rec.frame_count} "
        f"events={rec.event_count} duration_ms={rec.duration_ms}"
    )


@main.command(help="녹화를 검사한다.")
@click.argument("recording_id", required=False)
@click.option("--list", "list_all", is_flag=True, help="전체 녹화 목록 표시")
@click.option("--format", "fmt", type=click.Choice(["json", "text"]), default="text")
def inspect(recording_id: str | None, list_all: bool, fmt: str) -> None:
    repo = RecordingRepo(db=get_db())
    if list_all or not recording_id:
        rows = repo.list()
        if fmt == "json":
            import dataclasses as _dc

            _console.print_json(
                json.dumps([_dc.asdict(r) for r in rows], default=str)
            )
        else:
            table = Table(title="recordings")
            table.add_column("id")
            table.add_column("task")
            table.add_column("frames", justify="right")
            table.add_column("events", justify="right")
            table.add_column("duration_ms", justify="right")
            for r in rows:
                table.add_row(
                    r.id, r.task_name, str(r.frame_count), str(r.event_count), str(r.duration_ms)
                )
            _console.print(table)
        return

    summary = repo.get(recording_id)
    if summary is None:
        raise click.ClickException(f"no such recording: {recording_id}")
    if fmt == "json":
        import dataclasses as _dc

        _console.print_json(json.dumps(_dc.asdict(summary), default=str))
        return
    _console.print(f"[bold]{summary.id}[/bold]")
    _console.print(f"  task:       {summary.task_name}")
    _console.print(f"  description: {summary.description}")
    _console.print(f"  created:    {summary.created_at}")
    _console.print(f"  resolution: {summary.resolution[0]}x{summary.resolution[1]} @ {summary.dpi_scale:.2f}x")
    _console.print(f"  target:     {summary.target_process}")
    _console.print(f"  frames:     {summary.frame_count}")
    _console.print(f"  events:     {summary.event_count}")
    _console.print(f"  steps:      {summary.step_count}")
    _console.print(f"  duration:   {summary.duration_ms} ms")


@main.command(help="녹화를 의미 단위(Step)로 변환한다.")
@click.argument("recording_id")
@click.option("--model", default=None, help="Captioner 모델 override")
@click.option(
    "--no-vlm",
    is_flag=True,
    default=False,
    help="VLM 호출 없이 룰 기반 캡션만 사용 (빠르지만 낮은 품질)",
)
@click.option(
    "--cluster-window",
    default=1.5,
    type=float,
    help="이벤트 클러스터링 시간 창 (초)",
)
def semanticize(
    recording_id: str, model: str | None, no_vlm: bool, cluster_window: float
) -> None:
    from macrobania.agent.captioner import Captioner
    from macrobania.recording import BuilderConfig
    from macrobania.recording import semanticize as do_semanticize

    settings = get_settings()
    rec_dir = settings.recordings_dir / recording_id
    if not rec_dir.exists():
        raise click.ClickException(f"recording directory not found: {rec_dir}")

    db = get_db()
    cfg = BuilderConfig(cluster_window_ns=int(cluster_window * 1e9))

    captioner: Captioner | None = None
    use_vlm = not no_vlm
    if use_vlm:
        try:
            captioner = Captioner.from_env()
            if model:
                captioner.model = model
        except Exception as e:
            _console.print(f"[yellow]captioner init failed ({e}); falling back to rule-based[/yellow]")
            use_vlm = False

    result = do_semanticize(
        db=db,
        rec_id=recording_id,
        rec_dir=rec_dir,
        captioner=captioner,
        cfg=cfg,
        use_vlm=use_vlm,
    )
    _console.print(
        f"[green]done[/green] rec={result.recording_id} "
        f"candidates={result.candidate_count} steps={result.step_count} "
        f"vlm={'yes' if use_vlm else 'no'}"
    )


@main.command(help="녹화를 HTML 뷰어로 익스포트")
@click.argument("recording_id")
@click.option("--out", "out_path", type=click.Path(path_type=Path), default=None)
def export_html(recording_id: str, out_path: Path | None) -> None:
    from macrobania.recording import export_html as do_export

    settings = get_settings()
    rec_dir = settings.recordings_dir / recording_id
    if not rec_dir.exists():
        raise click.ClickException(f"recording directory not found: {rec_dir}")

    out_path = out_path or (rec_dir / "viewer.html")
    do_export(db=get_db(), rec_id=recording_id, rec_dir=rec_dir, out_path=out_path)
    _console.print(f"[green]wrote[/green] {out_path}")


@main.command(help="녹화를 재생한다.")
@click.argument("recording_id")
@click.option("--mode", type=click.Choice(["a", "b", "c"], case_sensitive=False), default="a")
@click.option("--dry-run/--execute", default=True, help="기본은 dry-run (실제 입력 주입 X)")
@click.option("--speed", default=1.0, type=click.FloatRange(0.25, 4.0))
@click.option(
    "--no-verify",
    is_flag=True,
    default=False,
    help="precondition/postcondition 검증 스킵 (VLM 호출 없음)",
)
def play(
    recording_id: str,
    mode: str,
    dry_run: bool,
    speed: float,
    no_verify: bool,
) -> None:
    from macrobania.agent.verifier import Verifier
    from macrobania.inputio import FailSafe, make_injector
    from macrobania.player import FaithfulPlayer, PlaySession

    settings = get_settings()
    rec_dir = settings.recordings_dir / recording_id
    if not rec_dir.exists():
        raise click.ClickException(f"recording directory not found: {rec_dir}")

    mode_l = mode.lower()

    injector = make_injector(dry_run=dry_run)
    failsafe = FailSafe()
    session = PlaySession(
        db=get_db(),
        recording_id=recording_id,
        mode=mode_l,  # type: ignore[arg-type]
        injector=injector,
        failsafe=failsafe,
    )

    verifier: Verifier | None = None
    if not no_verify:
        try:
            verifier = Verifier.from_env()
        except Exception as e:
            _console.print(
                f"[yellow]verifier init failed ({e}); continuing without verification[/yellow]"
            )

    if mode_l == "a":
        player_a = FaithfulPlayer(
            session=session, rec_dir=rec_dir, verifier=verifier, speed=speed
        )
        _console.print(
            f"[green]playing[/green] rec={recording_id} mode=a speed={speed:.2f} "
            f"dry_run={dry_run} verify={bool(verifier)}"
        )
        result = player_a.play()
    elif mode_l == "b":
        from macrobania.agent.grounder import Grounder
        from macrobania.perception import OCREngine, UIASnapshotter
        from macrobania.player import GroundedPlayer

        try:
            grounder = Grounder.from_env()
        except Exception as e:
            raise click.ClickException(
                f"Grounder init failed (Ollama 실행 중인지 확인): {e}"
            ) from e

        uia = UIASnapshotter()
        ocr = OCREngine()
        player_b = GroundedPlayer(
            session=session,
            rec_dir=rec_dir,
            grounder=grounder,
            verifier=verifier,
            uia=uia if uia.available() else None,
            ocr=ocr if ocr.available() else None,
        )
        _console.print(
            f"[green]playing[/green] rec={recording_id} mode=b dry_run={dry_run} "
            f"uia={player_b.uia is not None} ocr={player_b.ocr is not None} "
            f"verify={bool(verifier)}"
        )
        result = player_b.play()
    else:  # mode_l == "c"
        raise click.ClickException(
            "Mode C is goal-driven; use `macrobania autonomous --goal ...` instead"
        )

    success = sum(1 for o in result.outcomes if o.status == "success")
    status = "[green]SUCCESS[/green]" if not result.failed else "[red]FAILED[/red]"
    _console.print(
        f"{status} session={result.session_id} "
        f"steps={len(result.outcomes)} success={success} "
        + (f"reason={result.failure_reason!r}" if result.failed else "")
    )


@main.command(help="현재 설정을 JSON으로 출력 (자동화용)")
def config_dump() -> None:
    settings = get_settings()
    data = settings.model_dump(mode="json")
    _console.print_json(json.dumps(data, default=str))


@main.command(help="PySide6 GUI 실행 (Phase 5)")
def gui() -> None:
    from macrobania.ui import run_gui

    sys.exit(run_gui())


@main.command(help="자율 모드 — 녹화 없이 자연어 goal로 실행 (Mode C, Phase 6)")
@click.option("--goal", required=True, help="자연어 목표 (예: '웹 페이지에서 일일 퀘스트 수령')")
@click.option("--max-steps", default=20, type=click.IntRange(1, 200))
@click.option("--dry-run/--execute", default=True)
@click.option("--planner-model", default=None, help="Planner 모델 override")
@click.option("--grounder-model", default=None, help="Grounder 모델 override")
def autonomous(
    goal: str,
    max_steps: int,
    dry_run: bool,
    planner_model: str | None,
    grounder_model: str | None,
) -> None:
    from macrobania.agent.grounder import Grounder
    from macrobania.agent.planner import Planner
    from macrobania.inputio import FailSafe, make_injector
    from macrobania.perception import OCREngine, UIASnapshotter
    from macrobania.player import AutonomousPlayer, PlaySession

    try:
        planner = Planner.from_env()
        if planner_model:
            planner.model = planner_model
    except Exception as e:
        raise click.ClickException(f"Planner init failed: {e}") from e
    try:
        grounder = Grounder.from_env()
        if grounder_model:
            grounder.model = grounder_model
    except Exception as e:
        raise click.ClickException(f"Grounder init failed: {e}") from e

    injector = make_injector(dry_run=dry_run)
    failsafe = FailSafe()
    # Mode C는 녹화 없이 실행되므로 recording_id는 합성 문자열
    synth_rec = "rec_autonomous_goal"
    from datetime import datetime

    from macrobania.models import Platform
    from macrobania.recording.writer import RecordingWriter

    db = get_db()
    conn = db.connect()
    row = conn.execute(
        "SELECT id FROM recordings WHERE id = ?", (synth_rec,)
    ).fetchone()
    if row is None:
        # 껍데기 Recording row를 만들어 FK 충돌 회피
        _ = RecordingWriter(
            db=db,
            rec_dir=get_settings().recordings_dir / synth_rec,
            rec_id=synth_rec,
            task_name="autonomous",
            platform=Platform(os="autonomous", resolution=(1, 1)),
        )
        _.create()
        _.finalize()
        _ = datetime.now  # 참조 유지
    session = PlaySession(
        db=db, recording_id=synth_rec, mode="c",
        injector=injector, failsafe=failsafe,
    )
    uia = UIASnapshotter()
    ocr = OCREngine()
    player = AutonomousPlayer(
        session=session,
        planner=planner,
        grounder=grounder,
        goal=goal,
        uia=uia if uia.available() else None,
        ocr=ocr if ocr.available() else None,
        max_steps=max_steps,
    )
    _console.print(
        f"[green]autonomous[/green] goal={goal!r} max_steps={max_steps} dry_run={dry_run}"
    )
    result = player.play()
    status = "[green]SUCCESS[/green]" if not result.failed else "[red]FAILED[/red]"
    success = sum(1 for o in result.outcomes if o.status == "success")
    _console.print(
        f"{status} session={result.session_id} steps={len(result.outcomes)} "
        f"success={success} "
        + (f"reason={result.failure_reason!r}" if result.failed else "")
    )


if __name__ == "__main__":
    main()
