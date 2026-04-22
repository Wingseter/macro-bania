"""녹화 조회 레포지토리."""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from macrobania.storage import Database


@dataclass(frozen=True)
class RecordingSummary:
    id: str
    task_name: str
    description: str
    created_at: str
    resolution: tuple[int, int]
    dpi_scale: float
    target_process: str | None
    frame_count: int
    event_count: int
    step_count: int
    duration_ms: int


@dataclass
class RecordingRepo:
    db: Database

    def list(self) -> list[RecordingSummary]:
        conn = self.db.connect()
        return [self._row_to_summary(row) for row in conn.execute(
            "SELECT id, task_name, description, created_at, resolution_w, resolution_h, "
            "dpi_scale, target_process, frame_count, event_count, step_count, duration_ms "
            "FROM recordings ORDER BY created_at DESC"
        )]

    def get(self, rec_id: str) -> RecordingSummary | None:
        conn = self.db.connect()
        row = conn.execute(
            "SELECT id, task_name, description, created_at, resolution_w, resolution_h, "
            "dpi_scale, target_process, frame_count, event_count, step_count, duration_ms "
            "FROM recordings WHERE id = ?",
            (rec_id,),
        ).fetchone()
        return self._row_to_summary(row) if row else None

    def delete(self, rec_id: str) -> bool:
        with self.db.transaction() as conn:
            cur = conn.execute("DELETE FROM recordings WHERE id = ?", (rec_id,))
            return cur.rowcount > 0

    def iter_events(self, rec_id: str) -> Iterator[dict[str, object]]:
        conn = self.db.connect()
        cur = conn.execute(
            "SELECT ts_ns, kind, x, y, button, vk, scan, extended, text, dx, dy, "
            "window_hwnd, window_title "
            "FROM raw_events WHERE recording_id = ? ORDER BY ts_ns",
            (rec_id,),
        )
        for row in cur:
            yield dict(row)

    def iter_frames(self, rec_id: str) -> Iterator[dict[str, object]]:
        conn = self.db.connect()
        cur = conn.execute(
            "SELECT ts_ns, path, is_keyframe, changed_bbox, uia_snapshot, ocr_snapshot "
            "FROM frames WHERE recording_id = ? ORDER BY ts_ns",
            (rec_id,),
        )
        for row in cur:
            yield dict(row)

    @staticmethod
    def _row_to_summary(row: object) -> RecordingSummary:
        return RecordingSummary(
            id=row["id"],  # type: ignore[index]
            task_name=row["task_name"],  # type: ignore[index]
            description=row["description"],  # type: ignore[index]
            created_at=row["created_at"],  # type: ignore[index]
            resolution=(int(row["resolution_w"]), int(row["resolution_h"])),  # type: ignore[index]
            dpi_scale=float(row["dpi_scale"]),  # type: ignore[index]
            target_process=row["target_process"],  # type: ignore[index]
            frame_count=int(row["frame_count"]),  # type: ignore[index]
            event_count=int(row["event_count"]),  # type: ignore[index]
            step_count=int(row["step_count"]),  # type: ignore[index]
            duration_ms=int(row["duration_ms"]),  # type: ignore[index]
        )
