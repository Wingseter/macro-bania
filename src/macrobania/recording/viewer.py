"""녹화 HTML 뷰어 익스포트.

독립 실행 가능한 단일 HTML 파일에 프레임·이벤트·스텝을 표시.
PySide6 GUI 전에 빠르게 검토 용도.
"""
from __future__ import annotations

import html
from pathlib import Path

from macrobania.logging import get_logger
from macrobania.recording.builder import load_steps
from macrobania.recording.repo import RecordingRepo
from macrobania.storage import Database

log = get_logger(__name__)


def export_html(db: Database, rec_id: str, *, rec_dir: Path, out_path: Path) -> Path:
    summary = RecordingRepo(db=db).get(rec_id)
    if summary is None:
        raise ValueError(f"no such recording: {rec_id}")

    steps = load_steps(db, rec_id)

    frames = list(RecordingRepo(db=db).iter_frames(rec_id))
    frames_html_items: list[str] = []
    for idx, row in enumerate(frames):
        rel = str(row["path"])  # type: ignore[index]
        is_key = bool(row["is_keyframe"])  # type: ignore[index]
        frames_html_items.append(
            f'<div class="frame {"kf" if is_key else ""}">'
            f'<div class="label">f{idx:05d} ts={row["ts_ns"]}{" [KEY]" if is_key else ""}</div>'  # type: ignore[index]
            f'<img src="{html.escape(rel)}" loading="lazy"/>'
            "</div>"
        )

    steps_html_items: list[str] = []
    for s in steps:
        steps_html_items.append(
            f'<tr>'
            f'<td>{s.index}</td>'
            f'<td>{html.escape(s.action.type.value)}</td>'
            f'<td>{html.escape(s.caption)}</td>'
            f'<td>{html.escape(s.action.target_description or "")}</td>'
            f'<td>{s.confidence:.2f}</td>'
            f'<td>{s.ts_start_ns}</td>'
            f'<td>{s.ts_end_ns}</td>'
            f"</tr>"
        )

    head = _HTML_HEAD.format(title=html.escape(summary.task_name))
    summary_block = (
        f"<h1>{html.escape(summary.task_name)}</h1>"
        f"<p><b>id:</b> {html.escape(summary.id)} &nbsp; "
        f"<b>resolution:</b> {summary.resolution[0]}x{summary.resolution[1]} @ "
        f"{summary.dpi_scale:.2f}x &nbsp; "
        f"<b>target:</b> {html.escape(summary.target_process or '-')}<br>"
        f"<b>description:</b> {html.escape(summary.description)}</p>"
        f"<p><b>frames:</b> {summary.frame_count} &nbsp; "
        f"<b>events:</b> {summary.event_count} &nbsp; "
        f"<b>steps:</b> {summary.step_count} &nbsp; "
        f"<b>duration:</b> {summary.duration_ms} ms</p>"
    )
    steps_table = (
        '<h2>Steps</h2><table class="steps"><thead><tr>'
        "<th>#</th><th>type</th><th>caption</th><th>target</th><th>conf</th>"
        "<th>ts_start</th><th>ts_end</th>"
        "</tr></thead><tbody>" + "".join(steps_html_items) + "</tbody></table>"
    )
    frames_grid = (
        '<h2>Frames</h2><div class="grid">' + "".join(frames_html_items) + "</div>"
    )

    body = summary_block + steps_table + frames_grid

    doc = head + f"<body>{body}</body></html>"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(doc, encoding="utf-8")
    log.info("viewer.export", rec_id=rec_id, out=str(out_path))
    return out_path


_HTML_HEAD = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8"/>
<title>{title} — macro-bania</title>
<style>
 body {{ font-family: system-ui, -apple-system, sans-serif; margin: 24px; color: #222; }}
 h1 {{ margin-bottom: 4px; }}
 .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
          gap: 8px; margin-top: 12px; }}
 .frame {{ border: 1px solid #ddd; padding: 4px; border-radius: 6px; background: #fafafa; }}
 .frame.kf {{ border-color: #c38; }}
 .frame .label {{ font-size: 12px; color: #666; margin-bottom: 4px; font-family: monospace; }}
 .frame img {{ width: 100%; height: auto; display: block; }}
 table.steps {{ border-collapse: collapse; margin-top: 8px; }}
 table.steps th, table.steps td {{ border: 1px solid #ddd; padding: 4px 8px; font-size: 14px; }}
 table.steps th {{ background: #eee; }}
 table.steps tr:nth-child(even) {{ background: #f7f7f7; }}
</style></head>"""
