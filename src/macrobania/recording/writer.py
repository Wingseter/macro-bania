"""녹화 Writer.

- SQLite에 Recording / RawEvent / Frame 행 기록
- 이미지는 ``<recordings_dir>/<rec_id>/frames/fNNNN.webp`` 로 저장
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PIL import Image

from macrobania.capture.backend import FrameData
from macrobania.logging import get_logger
from macrobania.models import Platform, RawEvent, Recording
from macrobania.safety.pii import PIIScrubber, scrub_text
from macrobania.storage import Database

log = get_logger(__name__)


@dataclass
class RecordingWriter:
    """한 개의 Recording을 디스크에 쓰는 책임자.

    사용법:
        writer = RecordingWriter(db=db, rec_dir=..., rec_id=..., platform=..., task_name=...)
        writer.create()
        writer.write_events([...])
        writer.write_frame(frame_data, is_keyframe=True)
        rec = writer.finalize()
    """

    db: Database
    rec_dir: Path
    rec_id: str
    task_name: str
    platform: Platform
    description: str = ""
    target_process: str | None = None
    target_window_title_regex: str | None = None
    pii_scrubber: PIIScrubber | None = None
    _frame_count: int = 0
    _event_count: int = 0
    _ts_first_ns: int | None = None
    _ts_last_ns: int | None = None
    _created: bool = False

    def __post_init__(self) -> None:
        self.rec_dir.mkdir(parents=True, exist_ok=True)
        (self.rec_dir / "frames").mkdir(exist_ok=True)
        (self.rec_dir / "uia").mkdir(exist_ok=True)
        (self.rec_dir / "ocr").mkdir(exist_ok=True)

    # --- lifecycle ---

    def create(self) -> None:
        if self._created:
            return
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO recordings
                    (id, task_name, description, created_at, os,
                     resolution_w, resolution_h, dpi_scale, primary_monitor,
                     target_process, target_window_title_regex)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    self.rec_id,
                    self.task_name,
                    self.description,
                    datetime.now().astimezone().isoformat(),
                    self.platform.os,
                    self.platform.resolution[0],
                    self.platform.resolution[1],
                    self.platform.dpi_scale,
                    self.platform.primary_monitor,
                    self.target_process,
                    self.target_window_title_regex,
                ),
            )
        self._created = True
        log.info("recording.created", rec_id=self.rec_id, dir=str(self.rec_dir))

    # --- writes ---

    def write_events(self, events: list[RawEvent]) -> None:
        if not events:
            return
        if not self._created:
            self.create()
        rows: list[tuple] = []
        for ev in events:
            text = ev.text
            if text and self.pii_scrubber is not None:
                text = self.pii_scrubber.scrub(text)
            elif text:
                text = scrub_text(text)
            rows.append(
                (
                    self.rec_id,
                    ev.ts_ns,
                    ev.kind.value,
                    ev.x,
                    ev.y,
                    ev.button,
                    ev.vk,
                    ev.scan,
                    ev.extended,
                    text,
                    ev.dx,
                    ev.dy,
                    ev.window_hwnd,
                    ev.window_title,
                )
            )
            self._track_ts(ev.ts_ns)
        with self.db.transaction() as conn:
            conn.executemany(
                """
                INSERT INTO raw_events
                    (recording_id, ts_ns, kind, x, y, button, vk, scan, extended,
                     text, dx, dy, window_hwnd, window_title)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                rows,
            )
        self._event_count += len(rows)

    def write_frame(
        self,
        frame: FrameData,
        *,
        is_keyframe: bool = False,
        changed_bbox: tuple[int, int, int, int] | None = None,
        uia_snapshot_json: str | None = None,
        ocr_snapshot_json: str | None = None,
    ) -> str:
        if not self._created:
            self.create()
        idx = self._frame_count
        rel_path = f"frames/f{idx:05d}.webp"
        abs_path = self.rec_dir / rel_path
        _save_webp(frame.image, abs_path)

        uia_rel = None
        if uia_snapshot_json is not None:
            uia_rel = f"uia/f{idx:05d}.json"
            (self.rec_dir / uia_rel).write_text(uia_snapshot_json, encoding="utf-8")

        ocr_rel = None
        if ocr_snapshot_json is not None:
            ocr_rel = f"ocr/f{idx:05d}.json"
            (self.rec_dir / ocr_rel).write_text(ocr_snapshot_json, encoding="utf-8")

        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO frames
                    (recording_id, ts_ns, path, is_keyframe, changed_bbox,
                     uia_snapshot, ocr_snapshot)
                VALUES (?,?,?,?,?,?,?)
                """,
                (
                    self.rec_id,
                    frame.ts_ns,
                    rel_path,
                    1 if is_keyframe else 0,
                    ",".join(map(str, changed_bbox)) if changed_bbox else None,
                    uia_rel,
                    ocr_rel,
                ),
            )
        self._track_ts(frame.ts_ns)
        self._frame_count += 1
        return rel_path

    def finalize(self) -> Recording:
        if not self._created:
            self.create()
        duration_ms = (
            ((self._ts_last_ns or 0) - (self._ts_first_ns or 0)) // 1_000_000
            if self._ts_first_ns is not None and self._ts_last_ns is not None
            else 0
        )
        with self.db.transaction() as conn:
            conn.execute(
                """
                UPDATE recordings SET
                    frame_count = ?,
                    event_count = ?,
                    duration_ms = ?
                WHERE id = ?
                """,
                (self._frame_count, self._event_count, duration_ms, self.rec_id),
            )
        log.info(
            "recording.finalized",
            rec_id=self.rec_id,
            frames=self._frame_count,
            events=self._event_count,
            duration_ms=duration_ms,
        )
        return Recording(
            id=self.rec_id,
            task_name=self.task_name,
            description=self.description,
            created_at=datetime.now().astimezone(),
            platform=self.platform,
            target_process=self.target_process,
            target_window_title_regex=self.target_window_title_regex,
            frame_count=self._frame_count,
            event_count=self._event_count,
            duration_ms=duration_ms,
        )

    # --- helpers ---

    def _track_ts(self, ts_ns: int) -> None:
        if self._ts_first_ns is None:
            self._ts_first_ns = ts_ns
        self._ts_last_ns = ts_ns


def _save_webp(image: Image.Image, path: Path) -> None:
    # lossless로 저장하되 너무 커지는 상황은 Phase 5에서 품질 slider로
    image.save(path, format="WEBP", method=4, quality=85)


def dumps(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
