"""ResourceAccess 層の共有部品：SQLite の接続とスキーマ（DD-03、EIF-02）。

`_` で始まるモジュールは、同じ層の実装だけが import できる（DD-01）。
IMMUTABLE の表には、UPDATE と DELETE を拒否するトリガーを付ける。
"""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);

CREATE TABLE IF NOT EXISTS measurement_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    outcome TEXT CHECK (outcome IN ('ok', 'rejected', 'failed')),
    CHECK ((finished_at IS NULL) = (outcome IS NULL))
);

CREATE TABLE IF NOT EXISTS account_snapshots (
    channel TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    run_id INTEGER NOT NULL REFERENCES measurement_runs(id),
    followers INTEGER NOT NULL,
    following INTEGER NOT NULL,
    posts INTEGER NOT NULL,
    PRIMARY KEY (channel, fetched_at)
);

CREATE TABLE IF NOT EXISTS post_metrics (
    channel TEXT NOT NULL,
    post_id TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    run_id INTEGER NOT NULL REFERENCES measurement_runs(id),
    created_at TEXT NOT NULL,
    text_head TEXT NOT NULL,
    impressions INTEGER,
    likes INTEGER,
    replies INTEGER,
    reposts INTEGER,
    quotes INTEGER,
    bookmarks INTEGER,
    profile_clicks INTEGER,
    link_clicks INTEGER,
    PRIMARY KEY (channel, post_id, fetched_at)
);

CREATE TABLE IF NOT EXISTS drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel TEXT NOT NULL,
    text TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    status TEXT NOT NULL,
    errors TEXT NOT NULL,
    warnings TEXT NOT NULL,
    estimate_usd TEXT NOT NULL,
    estimate_jpy INTEGER NOT NULL,
    estimate_usages TEXT NOT NULL,
    created_at TEXT NOT NULL,
    approved_at TEXT,
    post_id TEXT,
    published_at TEXT,
    error TEXT
);

CREATE TABLE IF NOT EXISTS charges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL,
    month TEXT NOT NULL,
    run_id INTEGER REFERENCES measurement_runs(id),
    draft_id INTEGER REFERENCES drafts(id),
    channel TEXT NOT NULL,
    usages TEXT NOT NULL,
    usd TEXT NOT NULL,
    jpy INTEGER NOT NULL,
    CHECK ((run_id IS NULL) != (draft_id IS NULL))
);

-- IMMUTABLE の表（DD-03）
CREATE TRIGGER IF NOT EXISTS account_snapshots_no_update BEFORE UPDATE ON account_snapshots
BEGIN SELECT RAISE(ABORT, 'account_snapshots is immutable'); END;
CREATE TRIGGER IF NOT EXISTS account_snapshots_no_delete BEFORE DELETE ON account_snapshots
BEGIN SELECT RAISE(ABORT, 'account_snapshots is immutable'); END;
CREATE TRIGGER IF NOT EXISTS post_metrics_no_update BEFORE UPDATE ON post_metrics
BEGIN SELECT RAISE(ABORT, 'post_metrics is immutable'); END;
CREATE TRIGGER IF NOT EXISTS post_metrics_no_delete BEFORE DELETE ON post_metrics
BEGIN SELECT RAISE(ABORT, 'post_metrics is immutable'); END;
CREATE TRIGGER IF NOT EXISTS charges_no_update BEFORE UPDATE ON charges
BEGIN SELECT RAISE(ABORT, 'charges is immutable'); END;
CREATE TRIGGER IF NOT EXISTS charges_no_delete BEFORE DELETE ON charges
BEGIN SELECT RAISE(ABORT, 'charges is immutable'); END;

-- MUTABLE の表も、変えてよい列と操作を絞る（DD-03）
CREATE TRIGGER IF NOT EXISTS drafts_fixed_columns BEFORE UPDATE OF channel, text, fingerprint, created_at ON drafts
BEGIN SELECT RAISE(ABORT, 'draft text and fingerprint are fixed'); END;
CREATE TRIGGER IF NOT EXISTS drafts_no_delete BEFORE DELETE ON drafts
BEGIN SELECT RAISE(ABORT, 'drafts are discarded by status, not deleted'); END;
CREATE TRIGGER IF NOT EXISTS measurement_runs_finish_once BEFORE UPDATE ON measurement_runs
WHEN OLD.finished_at IS NOT NULL
BEGIN SELECT RAISE(ABORT, 'measurement run already finished'); END;
CREATE TRIGGER IF NOT EXISTS measurement_runs_no_delete BEFORE DELETE ON measurement_runs
BEGIN SELECT RAISE(ABORT, 'measurement_runs cannot be deleted'); END;
"""


def connect(path: Path | str) -> sqlite3.Connection:
    """接続を開き、スキーマがなければ作る。`:memory:` も渡せる（テスト用）。"""
    if isinstance(path, Path):
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None)  # 自動コミット。複数の書き込みは CMP-A07 でまとめる（DD-21）
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    row = conn.execute("SELECT version FROM schema_version").fetchone()
    if row is None:
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
    elif row["version"] != SCHEMA_VERSION:
        raise RuntimeError(f"保存先のスキーマの版が違います（{row['version']}、期待は {SCHEMA_VERSION}）")
    return conn


@contextmanager
def savepoint(conn: sqlite3.Connection, name: str) -> Generator[None]:
    """1 つの操作の中の複数の文を、まとめて確定する。CMP-A07 のトランザクションの中でも外でも使える（DD-21）。"""
    conn.execute(f"SAVEPOINT {name}")
    try:
        yield
    except BaseException:
        conn.execute(f"ROLLBACK TO {name}")
        conn.execute(f"RELEASE {name}")
        raise
    conn.execute(f"RELEASE {name}")
