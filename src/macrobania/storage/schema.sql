-- macro-bania SQLite 스키마
-- 버전: 1 (P0). PLAN.md §10 데이터 스키마 반영.
-- 마이그레이션은 user_version pragma로 관리.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA user_version = 1;

CREATE TABLE IF NOT EXISTS recordings (
    id                          TEXT PRIMARY KEY,
    task_name                   TEXT NOT NULL,
    description                 TEXT NOT NULL DEFAULT '',
    created_at                  TEXT NOT NULL,      -- ISO8601
    os                          TEXT NOT NULL,
    resolution_w                INTEGER NOT NULL,
    resolution_h                INTEGER NOT NULL,
    dpi_scale                   REAL NOT NULL DEFAULT 1.0,
    primary_monitor             INTEGER NOT NULL DEFAULT 0,
    target_process              TEXT,
    target_window_title_regex   TEXT,
    frame_count                 INTEGER NOT NULL DEFAULT 0,
    event_count                 INTEGER NOT NULL DEFAULT 0,
    duration_ms                 INTEGER NOT NULL DEFAULT 0,
    step_count                  INTEGER NOT NULL DEFAULT 0,
    state_graph_id              TEXT
);

CREATE TABLE IF NOT EXISTS raw_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    recording_id    TEXT NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
    ts_ns           INTEGER NOT NULL,
    kind            TEXT NOT NULL,
    x               INTEGER,
    y               INTEGER,
    button          TEXT,
    vk              INTEGER,
    scan            INTEGER,
    extended        INTEGER,
    text            TEXT,
    dx              INTEGER,
    dy              INTEGER,
    window_hwnd     TEXT,
    window_title    TEXT
);
CREATE INDEX IF NOT EXISTS idx_raw_events_rec_ts ON raw_events(recording_id, ts_ns);

CREATE TABLE IF NOT EXISTS frames (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    recording_id    TEXT NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
    ts_ns           INTEGER NOT NULL,
    path            TEXT NOT NULL,          -- 저장소 루트 기준 상대경로 (WebP)
    is_keyframe     INTEGER NOT NULL DEFAULT 0,
    changed_bbox    TEXT,                   -- "x1,y1,x2,y2" 또는 NULL
    uia_snapshot    TEXT,                   -- JSON 파일 경로
    ocr_snapshot    TEXT                    -- JSON 파일 경로
);
CREATE INDEX IF NOT EXISTS idx_frames_rec_ts ON frames(recording_id, ts_ns);

CREATE TABLE IF NOT EXISTS steps (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    recording_id    TEXT NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
    step_index      INTEGER NOT NULL,
    ts_start_ns     INTEGER NOT NULL,
    ts_end_ns       INTEGER NOT NULL,
    frame_before    TEXT,
    frame_after     TEXT,
    action_json     TEXT NOT NULL,          -- Action pydantic model dump
    caption         TEXT NOT NULL DEFAULT '',
    precondition    TEXT,
    postcondition   TEXT,
    confidence      REAL NOT NULL DEFAULT 0.0,
    raw_event_ids   TEXT NOT NULL DEFAULT '[]'   -- JSON array of integers
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_steps_rec_idx ON steps(recording_id, step_index);

-- 감사 로그: 모든 입력 주입 기록
CREATE TABLE IF NOT EXISTS audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_ns           INTEGER NOT NULL,
    event_kind      TEXT NOT NULL,          -- "play_start", "inject_click", "dry_run_click", "kill_switch", ...
    recording_id    TEXT,
    step_index      INTEGER,
    details_json    TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(ts_ns);

-- 실행 세션 (Play 한 번당 1개)
CREATE TABLE IF NOT EXISTS sessions (
    id              TEXT PRIMARY KEY,
    recording_id    TEXT NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
    started_at      TEXT NOT NULL,
    ended_at        TEXT,
    mode            TEXT NOT NULL,          -- "a"|"b"|"c"
    dry_run         INTEGER NOT NULL DEFAULT 1,
    outcome         TEXT,                   -- "success"|"failed"|"aborted"
    failure_reason  TEXT
);
