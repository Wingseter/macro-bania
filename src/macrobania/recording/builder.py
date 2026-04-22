"""Raw event → Semantic Step 변환.

PLAN.md §11 후처리:
  1. 이벤트를 시간 창(default 1.5s)으로 클러스터링 → 후보 Step
  2. 각 후보에 대해 frame_before, frame_after + (VLM) caption
  3. DB steps 테이블에 저장
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from macrobania.agent.captioner import CandidateStep, Captioner
from macrobania.logging import get_logger
from macrobania.models import EventKind, RawEvent, Step
from macrobania.storage import Database

log = get_logger(__name__)


@dataclass
class BuilderConfig:
    cluster_window_ns: int = 1_500_000_000  # 1.5s
    min_events_for_step: int = 1
    mouse_move_only_is_step: bool = False  # 이동만 있으면 step 만들지 않음


@dataclass
class FramesIndex:
    """recording id의 ts_ns → frame path 매핑.

    재생/캡션 시 ``before``/``after`` 프레임을 찾는 데 사용.
    """

    entries: list[tuple[int, str]]  # (ts_ns, relative_path) — ts 오름차순

    def frame_before(self, ts_ns: int) -> str | None:
        best: str | None = None
        for ts, path in self.entries:
            if ts <= ts_ns:
                best = path
            else:
                break
        return best

    def frame_after(self, ts_ns: int) -> str | None:
        for ts, path in self.entries:
            if ts > ts_ns:
                return path
        # 마지막 프레임 fallback
        return self.entries[-1][1] if self.entries else None


def load_frames_index(db: Database, rec_id: str) -> FramesIndex:
    conn = db.connect()
    rows = conn.execute(
        "SELECT ts_ns, path FROM frames WHERE recording_id = ? ORDER BY ts_ns",
        (rec_id,),
    ).fetchall()
    return FramesIndex(entries=[(int(r[0]), str(r[1])) for r in rows])


def load_events(db: Database, rec_id: str) -> list[tuple[int, RawEvent]]:
    """(row_id, RawEvent) 순차. 라디칼하게 Pydantic 재구성."""
    conn = db.connect()
    cur = conn.execute(
        "SELECT id, ts_ns, kind, x, y, button, vk, scan, extended, text, dx, dy, "
        "window_hwnd, window_title "
        "FROM raw_events WHERE recording_id = ? ORDER BY ts_ns",
        (rec_id,),
    )
    out: list[tuple[int, RawEvent]] = []
    for row in cur:
        ev = RawEvent(
            ts_ns=int(row["ts_ns"]),
            kind=EventKind(str(row["kind"])),
            x=row["x"],
            y=row["y"],
            button=row["button"],
            vk=row["vk"],
            scan=row["scan"],
            extended=row["extended"],
            text=row["text"],
            dx=row["dx"],
            dy=row["dy"],
            window_hwnd=row["window_hwnd"],
            window_title=row["window_title"],
        )
        out.append((int(row["id"]), ev))
    return out


def cluster(
    events: list[tuple[int, RawEvent]],
    *,
    cfg: BuilderConfig | None = None,
    frames: FramesIndex | None = None,
) -> list[CandidateStep]:
    """이벤트를 시간 창으로 클러스터링.

    MOUSE_MOVE-only 클러스터는 ``cfg.mouse_move_only_is_step=False`` 시 drop.
    """
    cfg = cfg or BuilderConfig()
    frames = frames or FramesIndex(entries=[])
    candidates: list[CandidateStep] = []
    current: list[tuple[int, RawEvent]] = []

    def _flush() -> None:
        if not current:
            return
        if not cfg.mouse_move_only_is_step:
            kinds = {e.kind for _, e in current}
            if kinds <= {EventKind.MOUSE_MOVE}:
                current.clear()
                return
        if len(current) < cfg.min_events_for_step:
            current.clear()
            return

        ids = [i for i, _ in current]
        evs = [e for _, e in current]
        ts_start = evs[0].ts_ns
        ts_end = evs[-1].ts_ns
        candidates.append(
            CandidateStep(
                ts_start_ns=ts_start,
                ts_end_ns=ts_end,
                events=evs,
                frame_before_path=frames.frame_before(ts_start),
                frame_after_path=frames.frame_after(ts_end),
                raw_event_ids=ids,
            )
        )
        current.clear()

    last_ts: int | None = None
    for row_id, ev in events:
        if last_ts is not None and (ev.ts_ns - last_ts) > cfg.cluster_window_ns:
            _flush()
        current.append((row_id, ev))
        last_ts = ev.ts_ns
    _flush()
    return candidates


@dataclass
class SemanticizeResult:
    recording_id: str
    candidate_count: int
    step_count: int


def semanticize(
    db: Database,
    rec_id: str,
    *,
    rec_dir: Path,
    captioner: Captioner | None = None,
    cfg: BuilderConfig | None = None,
    use_vlm: bool = True,
) -> SemanticizeResult:
    """녹화 하나를 Step으로 변환해 DB에 저장.

    기존 Step이 있으면 교체 (recording_id로 DELETE 후 INSERT).
    """
    cfg = cfg or BuilderConfig()
    frames_idx = load_frames_index(db, rec_id)
    events = load_events(db, rec_id)
    candidates = cluster(events, cfg=cfg, frames=frames_idx)
    log.info("semanticize.start", rec_id=rec_id, candidates=len(candidates), use_vlm=use_vlm)

    # 기존 steps 제거
    with db.transaction() as conn:
        conn.execute("DELETE FROM steps WHERE recording_id = ?", (rec_id,))

    steps: list[Step] = []
    captioner_instance: Captioner | None = None
    if use_vlm:
        captioner_instance = captioner or Captioner.from_env()
    for idx, cand in enumerate(candidates):
        before_img: Image.Image | None = None
        after_img: Image.Image | None = None
        if use_vlm and cand.frame_before_path:
            before_img = _safe_open(rec_dir / cand.frame_before_path)
        if use_vlm and cand.frame_after_path:
            after_img = _safe_open(rec_dir / cand.frame_after_path)
        if captioner_instance is not None and before_img and after_img:
            try:
                step = captioner_instance.caption(
                    cand, frame_before_img=before_img, frame_after_img=after_img
                )
            except Exception as e:
                log.warning("captioner.failed_fallback_rule", error=str(e))
                from macrobania.agent.captioner import rule_based_step

                step = rule_based_step(cand)
        else:
            from macrobania.agent.captioner import rule_based_step

            step = rule_based_step(cand)
        step = dataclasses_replace(step, index=idx)
        steps.append(step)

    with db.transaction() as conn:
        for step in steps:
            conn.execute(
                """
                INSERT INTO steps
                    (recording_id, step_index, ts_start_ns, ts_end_ns,
                     frame_before, frame_after, action_json, caption,
                     precondition, postcondition, confidence, raw_event_ids)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    rec_id,
                    step.index,
                    step.ts_start_ns,
                    step.ts_end_ns,
                    step.frame_before,
                    step.frame_after,
                    step.action.model_dump_json(),
                    step.caption,
                    step.precondition,
                    step.postcondition,
                    step.confidence,
                    json.dumps(step.raw_event_ids),
                ),
            )
        conn.execute(
            "UPDATE recordings SET step_count = ? WHERE id = ?",
            (len(steps), rec_id),
        )
    log.info("semanticize.done", rec_id=rec_id, step_count=len(steps))
    return SemanticizeResult(recording_id=rec_id, candidate_count=len(candidates), step_count=len(steps))


def load_steps(db: Database, rec_id: str) -> list[Step]:
    from macrobania.models import Action

    conn = db.connect()
    cur = conn.execute(
        "SELECT step_index, ts_start_ns, ts_end_ns, frame_before, frame_after, "
        "action_json, caption, precondition, postcondition, confidence, raw_event_ids "
        "FROM steps WHERE recording_id = ? ORDER BY step_index",
        (rec_id,),
    )
    out: list[Step] = []
    for row in cur:
        action = Action.model_validate_json(row["action_json"])
        out.append(
            Step(
                index=int(row["step_index"]),
                ts_start_ns=int(row["ts_start_ns"]),
                ts_end_ns=int(row["ts_end_ns"]),
                frame_before=row["frame_before"],
                frame_after=row["frame_after"],
                raw_event_ids=json.loads(row["raw_event_ids"] or "[]"),
                action=action,
                caption=row["caption"] or "",
                precondition=row["precondition"],
                postcondition=row["postcondition"],
                confidence=float(row["confidence"] or 0.0),
            )
        )
    return out


def _safe_open(path: Path) -> Image.Image | None:
    try:
        return Image.open(path).convert("RGB")
    except Exception:
        return None


def dataclasses_replace(obj: Step, **kwargs: object) -> Step:
    """Pydantic v2에서도 쉽게 copy + override."""
    data = obj.model_dump()
    data.update(kwargs)
    return Step.model_validate(data)
