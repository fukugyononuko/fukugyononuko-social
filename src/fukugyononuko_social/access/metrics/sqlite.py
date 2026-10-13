"""CMP-A02 MetricsAccess の実装：SQLite（DD-03）。数字の表は追記だけ。"""

import sqlite3
from collections.abc import Sequence
from datetime import datetime

from fukugyononuko_social.domain.channel import Channel
from fukugyononuko_social.domain.errors import Outcome
from fukugyononuko_social.domain.metrics import (
    AccountSnapshot,
    Finished,
    MeasurementRun,
    MetricsHistory,
    PostMetrics,
    Running,
)

POST_COLUMNS = ("impressions", "likes", "replies", "reposts", "quotes", "bookmarks", "profile_clicks", "link_clicks")


def _t(s: str) -> datetime:
    return datetime.fromisoformat(s)


class SqliteMetricsAccess:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def start_run(self, at: datetime) -> int:
        cur = self._conn.execute("INSERT INTO measurement_runs (started_at) VALUES (?)", (at.isoformat(),))
        assert cur.lastrowid is not None
        return cur.lastrowid

    def finish_run(self, run_id: int, at: datetime, outcome: Outcome) -> None:
        self._conn.execute(
            "UPDATE measurement_runs SET finished_at = ?, outcome = ? WHERE id = ?", (at.isoformat(), outcome.value, run_id)
        )

    def record(self, run_id: int, accounts: Sequence[AccountSnapshot], posts: Sequence[PostMetrics]) -> None:
        with self._conn:
            self._conn.execute("BEGIN")
            # 同じ主キー（同じ時刻の取得）は重複させない（NFR-05）。IMMUTABLE なので REPLACE は使わない
            self._conn.executemany(
                "INSERT OR IGNORE INTO account_snapshots (channel, fetched_at, run_id, followers, following, posts)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                [(a.channel.value, a.fetched_at.isoformat(), run_id, a.followers, a.following, a.posts) for a in accounts],
            )
            self._conn.executemany(
                "INSERT OR IGNORE INTO post_metrics (channel, post_id, fetched_at, run_id, created_at, text_head, "
                + ", ".join(POST_COLUMNS)
                + ") VALUES (?, ?, ?, ?, ?, ?, "
                + ", ".join("?" * len(POST_COLUMNS))
                + ")",
                [
                    (p.channel.value, p.post_id, p.fetched_at.isoformat(), run_id, p.created_at.isoformat(), p.text_head)
                    + tuple(getattr(p, c) for c in POST_COLUMNS)
                    for p in posts
                ],
            )

    def history(self) -> MetricsHistory:
        accounts = tuple(
            AccountSnapshot(Channel(r["channel"]), _t(r["fetched_at"]), r["followers"], r["following"], r["posts"])
            for r in self._conn.execute("SELECT * FROM account_snapshots ORDER BY fetched_at, channel")
        )
        posts = tuple(
            PostMetrics(
                channel=Channel(r["channel"]),
                post_id=r["post_id"],
                created_at=_t(r["created_at"]),
                fetched_at=_t(r["fetched_at"]),
                text_head=r["text_head"],
                **{c: r[c] for c in POST_COLUMNS},
            )
            for r in self._conn.execute("SELECT * FROM post_metrics ORDER BY fetched_at, channel, post_id")
        )
        last = self._conn.execute("SELECT * FROM measurement_runs ORDER BY id DESC LIMIT 1").fetchone()
        run: MeasurementRun | None = None
        if last is not None:
            if last["finished_at"] is None:
                run = Running(last["id"], _t(last["started_at"]))
            else:
                run = Finished(last["id"], _t(last["started_at"]), _t(last["finished_at"]), Outcome(last["outcome"]))
        return MetricsHistory(accounts=accounts, posts=posts, last_run=run)
