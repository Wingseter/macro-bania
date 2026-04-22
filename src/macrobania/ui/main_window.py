"""macro-bania GUI (최소 동작 버전).

Tabs: Library / Record / Play / Logs
모든 동작은 CLI와 동일 코드를 호출 (이중 구현 회피).
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path

from macrobania.config import get_settings
from macrobania.logging import configure_logging, get_logger
from macrobania.recording import RecordingRepo
from macrobania.storage import get_db

log = get_logger(__name__)


def _ensure_pyside() -> object:
    try:
        from PySide6 import QtWidgets

        return QtWidgets
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "PySide6 미설치 — `uv sync --extra ui` 후 다시 시도"
        ) from e


def _library_tab(QtWidgets: object) -> object:
    """녹화 목록 탭."""
    w = QtWidgets.QWidget()  # type: ignore[attr-defined]
    layout = QtWidgets.QVBoxLayout(w)  # type: ignore[attr-defined]

    label = QtWidgets.QLabel("<h2>Recordings</h2>")  # type: ignore[attr-defined]
    layout.addWidget(label)

    table = QtWidgets.QTableWidget()  # type: ignore[attr-defined]
    table.setColumnCount(5)
    table.setHorizontalHeaderLabels(["id", "task", "frames", "events", "duration_ms"])
    table.horizontalHeader().setStretchLastSection(True)
    layout.addWidget(table)

    def refresh() -> None:
        repo = RecordingRepo(db=get_db())
        rows = repo.list()
        table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            table.setItem(i, 0, QtWidgets.QTableWidgetItem(r.id))  # type: ignore[attr-defined]
            table.setItem(i, 1, QtWidgets.QTableWidgetItem(r.task_name))  # type: ignore[attr-defined]
            table.setItem(i, 2, QtWidgets.QTableWidgetItem(str(r.frame_count)))  # type: ignore[attr-defined]
            table.setItem(i, 3, QtWidgets.QTableWidgetItem(str(r.event_count)))  # type: ignore[attr-defined]
            table.setItem(i, 4, QtWidgets.QTableWidgetItem(str(r.duration_ms)))  # type: ignore[attr-defined]
        table.resizeColumnsToContents()

    refresh_btn = QtWidgets.QPushButton("Refresh")  # type: ignore[attr-defined]
    refresh_btn.clicked.connect(refresh)
    layout.addWidget(refresh_btn)

    refresh()
    return w


def _record_tab(QtWidgets: object) -> object:
    """녹화 시작 탭."""
    from macrobania.recording import RecordingSession
    from macrobania.recording.session import RecorderConfig

    w = QtWidgets.QWidget()  # type: ignore[attr-defined]
    layout = QtWidgets.QFormLayout(w)  # type: ignore[attr-defined]

    name_edit = QtWidgets.QLineEdit("my-task")  # type: ignore[attr-defined]
    desc_edit = QtWidgets.QLineEdit()  # type: ignore[attr-defined]
    target_edit = QtWidgets.QLineEdit()  # type: ignore[attr-defined]
    fps_spin = QtWidgets.QSpinBox()  # type: ignore[attr-defined]
    fps_spin.setRange(1, 30)
    fps_spin.setValue(6)
    duration_spin = QtWidgets.QDoubleSpinBox()  # type: ignore[attr-defined]
    duration_spin.setRange(0.0, 3600.0)
    duration_spin.setDecimals(1)
    duration_spin.setValue(5.0)

    status = QtWidgets.QLabel("idle")  # type: ignore[attr-defined]
    start_btn = QtWidgets.QPushButton("Start (blocking)")  # type: ignore[attr-defined]
    stop_btn = QtWidgets.QPushButton("Stop")  # type: ignore[attr-defined]
    stop_btn.setEnabled(False)

    layout.addRow("Task name", name_edit)
    layout.addRow("Description", desc_edit)
    layout.addRow("Target process", target_edit)
    layout.addRow("FPS", fps_spin)
    layout.addRow("Duration (s)", duration_spin)
    layout.addRow(start_btn)
    layout.addRow(stop_btn)
    layout.addRow(status)

    state: dict[str, object] = {"session": None, "thread": None}

    def _run(session: RecordingSession) -> None:
        try:
            rec = session.run()
            status.setText(f"done id={rec.id} frames={rec.frame_count}")
        except Exception as e:
            status.setText(f"error: {e}")
        finally:
            start_btn.setEnabled(True)
            stop_btn.setEnabled(False)

    def start() -> None:
        session = RecordingSession(
            task_name=name_edit.text(),
            description=desc_edit.text(),
            target_process=target_edit.text() or None,
            cfg=RecorderConfig(capture_fps=fps_spin.value()),
        )
        state["session"] = session
        dur = duration_spin.value()
        if dur > 0:
            threading.Timer(dur, session.stop).start()
        t = threading.Thread(target=_run, args=(session,), daemon=True)
        state["thread"] = t
        t.start()
        start_btn.setEnabled(False)
        stop_btn.setEnabled(True)
        status.setText("recording…")

    def stop() -> None:
        sess = state.get("session")
        if sess is not None:
            sess.stop()  # type: ignore[attr-defined]

    start_btn.clicked.connect(start)
    stop_btn.clicked.connect(stop)
    return w


def _play_tab(QtWidgets: object) -> object:
    """재생 탭 (Dry-run 기본)."""
    w = QtWidgets.QWidget()  # type: ignore[attr-defined]
    layout = QtWidgets.QFormLayout(w)  # type: ignore[attr-defined]

    rec_combo = QtWidgets.QComboBox()  # type: ignore[attr-defined]
    mode_combo = QtWidgets.QComboBox()  # type: ignore[attr-defined]
    mode_combo.addItems(["a (Faithful)", "b (Grounded)"])
    dry_chk = QtWidgets.QCheckBox("Dry run")  # type: ignore[attr-defined]
    dry_chk.setChecked(True)
    speed_spin = QtWidgets.QDoubleSpinBox()  # type: ignore[attr-defined]
    speed_spin.setRange(0.25, 4.0)
    speed_spin.setSingleStep(0.25)
    speed_spin.setValue(1.0)

    status = QtWidgets.QLabel("idle")  # type: ignore[attr-defined]
    play_btn = QtWidgets.QPushButton("Play")  # type: ignore[attr-defined]

    layout.addRow("Recording", rec_combo)
    layout.addRow("Mode", mode_combo)
    layout.addRow("Speed", speed_spin)
    layout.addRow(dry_chk)
    layout.addRow(play_btn)
    layout.addRow(status)

    def refresh_list() -> None:
        rec_combo.clear()
        for r in RecordingRepo(db=get_db()).list():
            rec_combo.addItem(r.id)

    refresh_list()

    def play() -> None:
        from macrobania.agent.grounder import Grounder
        from macrobania.inputio import FailSafe, make_injector
        from macrobania.perception import OCREngine, UIASnapshotter
        from macrobania.player import FaithfulPlayer, GroundedPlayer, PlaySession

        rec_id = rec_combo.currentText()
        if not rec_id:
            status.setText("no recording selected")
            return
        mode_l = "a" if mode_combo.currentText().startswith("a") else "b"
        dry = dry_chk.isChecked()
        speed = speed_spin.value()

        settings = get_settings()
        rec_dir = settings.recordings_dir / rec_id

        session = PlaySession(
            db=get_db(),
            recording_id=rec_id,
            mode=mode_l,  # type: ignore[arg-type]
            injector=make_injector(dry_run=dry),
            failsafe=FailSafe(),
        )
        status.setText(f"playing {rec_id} mode={mode_l} dry={dry}")

        def _run() -> None:
            try:
                if mode_l == "a":
                    result = FaithfulPlayer(
                        session=session,
                        rec_dir=rec_dir,
                        verifier=None,
                        speed=speed,
                    ).play()
                else:
                    try:
                        grounder = Grounder.from_env()
                    except Exception as e:
                        status.setText(f"grounder init failed: {e}")
                        return
                    uia = UIASnapshotter()
                    ocr = OCREngine()
                    result = GroundedPlayer(
                        session=session,
                        rec_dir=rec_dir,
                        grounder=grounder,
                        verifier=None,
                        uia=uia if uia.available() else None,
                        ocr=ocr if ocr.available() else None,
                    ).play()
                tag = "OK" if not result.failed else "FAIL"
                status.setText(
                    f"{tag} steps={len(result.outcomes)} "
                    f"success={sum(1 for o in result.outcomes if o.status == 'success')}"
                )
            except Exception as e:
                status.setText(f"error: {e}")

        threading.Thread(target=_run, daemon=True).start()

    play_btn.clicked.connect(play)
    return w


def _logs_tab(QtWidgets: object) -> object:
    from PySide6 import QtCore

    w = QtWidgets.QWidget()  # type: ignore[attr-defined]
    layout = QtWidgets.QVBoxLayout(w)  # type: ignore[attr-defined]
    layout.addWidget(QtWidgets.QLabel("<h2>Audit Log</h2>"))  # type: ignore[attr-defined]

    view = QtWidgets.QPlainTextEdit()  # type: ignore[attr-defined]
    view.setReadOnly(True)
    view.setPlaceholderText("Refresh를 눌러 최근 감사 로그를 불러온다.")
    layout.addWidget(view)

    btn = QtWidgets.QPushButton("Refresh")  # type: ignore[attr-defined]
    layout.addWidget(btn)

    def refresh() -> None:
        path: Path = get_settings().audit_log_path
        if not path.exists():
            view.setPlainText("(no audit log yet)")
            return
        text = path.read_text(encoding="utf-8", errors="replace")
        # 최근 200줄만
        lines = text.splitlines()[-200:]
        view.setPlainText("\n".join(lines))
        view.verticalScrollBar().setValue(view.verticalScrollBar().maximum())
        _ = QtCore  # 참조 유지

    btn.clicked.connect(refresh)
    refresh()
    return w


def main() -> int:
    QtWidgets = _ensure_pyside()
    configure_logging()

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)  # type: ignore[attr-defined]
    win = QtWidgets.QMainWindow()  # type: ignore[attr-defined]
    win.setWindowTitle("macro-bania")
    win.resize(900, 600)

    tabs = QtWidgets.QTabWidget()  # type: ignore[attr-defined]
    tabs.addTab(_library_tab(QtWidgets), "Library")
    tabs.addTab(_record_tab(QtWidgets), "Record")
    tabs.addTab(_play_tab(QtWidgets), "Play")
    tabs.addTab(_logs_tab(QtWidgets), "Logs")

    # 상단 경고 바
    central = QtWidgets.QWidget()  # type: ignore[attr-defined]
    layout = QtWidgets.QVBoxLayout(central)  # type: ignore[attr-defined]
    warning = QtWidgets.QLabel(  # type: ignore[attr-defined]
        "<b style='color:#c33;'>⚠ 본 도구는 자동 입력을 주입합니다.</b> "
        "커널 안티치트 게임에 사용하지 마세요. "
        "결제/송금/삭제는 휴먼 컨펌이 필요합니다."
    )
    warning.setWordWrap(True)
    layout.addWidget(warning)
    layout.addWidget(tabs)
    win.setCentralWidget(central)

    win.show()
    return int(app.exec())


if __name__ == "__main__":
    sys.exit(main())
