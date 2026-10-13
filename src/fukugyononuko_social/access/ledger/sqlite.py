"""CMP-A04 LedgerAccess の実装：SQLite（DD-03 charges、IMMUTABLE）。"""

import json
import sqlite3
from collections.abc import Mapping
from datetime import datetime

from fukugyononuko_social.domain.channel import Channel, month_of
from fukugyononuko_social.domain.money import Cost


class SqliteLedgerAccess:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def record_charge(self, at: datetime, cost: Cost, *, run_id: int | None = None, draft_id: int | None = None) -> None:
        channels = {u.channel for u in cost.usages}
        if len(channels) != 1:
            raise ValueError("1 件の費用の記録には、1 つのチャネルの操作だけを入れる")
        if (run_id is None) == (draft_id is None):
            raise ValueError("費用は、計測（run_id）か投稿（draft_id）のどちらか一方に結びつける")
        usages = [{"operation": u.operation, "units": u.units} for u in cost.usages]
        self._conn.execute(
            "INSERT INTO charges (at, month, run_id, draft_id, channel, usages, usd, jpy) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (at.isoformat(), month_of(at), run_id, draft_id, channels.pop().value, json.dumps(usages), str(cost.usd), cost.jpy),
        )

    def month_total_jpy(self, month: str) -> int:
        row = self._conn.execute("SELECT COALESCE(SUM(jpy), 0) AS total FROM charges WHERE month = ?", (month,)).fetchone()
        return int(row["total"])

    def totals_by_month_and_channel(self) -> Mapping[tuple[str, Channel], int]:
        rows = self._conn.execute("SELECT month, channel, SUM(jpy) AS total FROM charges GROUP BY month, channel")
        return {(r["month"], Channel(r["channel"])): int(r["total"]) for r in rows}
