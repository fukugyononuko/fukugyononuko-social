"""CMP-A03 DraftAccess の実装：SQLite（DD-03 drafts、DD-04）。

保存先の行と、直和型の DraftState との変換をここで 1 回だけ行う。
遷移は `UPDATE … WHERE id = ? AND status IN (許す元の状態)` で行い、更新した行が 0 なら拒否する（NFR-06）。
"""

import json
import sqlite3
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from fukugyononuko_social.domain.channel import Channel
from fukugyononuko_social.domain.drafts import (
    Approved,
    Discarded,
    Draft,
    DraftState,
    DraftStatus,
    Fail,
    Failed,
    Finding,
    Pass,
    Pending,
    Published,
    Rejected,
    Sending,
    Severity,
    Verdict,
    fingerprint,
)
from fukugyononuko_social.domain.errors import BusinessRejection
from fukugyononuko_social.domain.money import Cost, Usage

S = DraftStatus


def _findings_json(findings: tuple[Finding, ...]) -> str:
    return json.dumps(
        [{"severity": f.severity.value, "code": f.code, "message": f.message} for f in findings], ensure_ascii=False
    )


def _findings(text: str) -> tuple[Finding, ...]:
    return tuple(Finding(Severity(f["severity"]), f["code"], f["message"]) for f in json.loads(text))


def _t(s: str | None) -> datetime:
    if s is None:
        raise ValueError("保存先の下書きに、状態に必要な時刻がありません")
    return datetime.fromisoformat(s)


def _state(row: sqlite3.Row) -> DraftState:
    match DraftStatus(row["status"]):
        case S.REJECTED:
            return Rejected(errors=_findings(row["errors"]))
        case S.PENDING:
            return Pending()
        case S.APPROVED:
            return Approved(_t(row["approved_at"]))
        case S.SENDING:
            return Sending(_t(row["approved_at"]))
        case S.PUBLISHED:
            return Published(_t(row["approved_at"]), row["post_id"], _t(row["published_at"]))
        case S.FAILED:
            return Failed(_t(row["approved_at"]), row["error"] or "")
        case S.DISCARDED:
            return Discarded()


def _draft(row: sqlite3.Row) -> Draft:
    channel = Channel(row["channel"])
    usages = tuple(Usage(channel, u["operation"], u["units"]) for u in json.loads(row["estimate_usages"]))
    return Draft(
        id=row["id"],
        channel=channel,
        text=row["text"],
        fingerprint=row["fingerprint"],
        warnings=_findings(row["warnings"]),
        estimate=Cost(usd=Decimal(row["estimate_usd"]), jpy=row["estimate_jpy"], usages=usages),
        created_at=_t(row["created_at"]),
        state=_state(row),
    )


class SqliteDraftAccess:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save_draft(self, channel: Channel, text: str, verdict: Verdict, estimate: Cost, at: datetime) -> Draft:
        match verdict:
            case Fail(errors=errors, warnings=warnings):
                status, error_list = S.REJECTED, errors
            case Pass(warnings=warnings):
                status, error_list = S.PENDING, ()
        usages = [{"operation": u.operation, "units": u.units} for u in estimate.usages]
        cur = self._conn.execute(
            "INSERT INTO drafts (channel, text, fingerprint, status, errors, warnings,"
            " estimate_usd, estimate_jpy, estimate_usages, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                channel.value,
                text,
                fingerprint(channel, text),
                status.value,
                _findings_json(error_list),
                _findings_json(warnings),
                str(estimate.usd),
                estimate.jpy,
                json.dumps(usages),
                at.isoformat(),
            ),
        )
        assert cur.lastrowid is not None
        return self.find(cur.lastrowid)

    def find(self, draft_id: int) -> Draft:
        row = self._conn.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,)).fetchone()
        if row is None:
            raise BusinessRejection(f"下書き {draft_id} はありません")
        return _draft(row)

    def drafts(self, status: DraftStatus | None = None) -> Sequence[Draft]:
        if status is None:
            rows = self._conn.execute("SELECT * FROM drafts ORDER BY id")
        else:
            rows = self._conn.execute("SELECT * FROM drafts WHERE status = ? ORDER BY id", (status.value,))
        return [_draft(r) for r in rows]

    def _transition(self, draft_id: int, sources: tuple[DraftStatus, ...], target: DraftStatus, **columns: str) -> Draft:
        current = self.find(draft_id)
        sets = ", ".join(["status = ?"] + [f"{c} = ?" for c in columns])
        marks = ", ".join("?" * len(sources))
        cur = self._conn.execute(
            f"UPDATE drafts SET {sets} WHERE id = ? AND status IN ({marks})",
            (target.value, *columns.values(), draft_id, *(s.value for s in sources)),
        )
        if cur.rowcount == 0:
            raise BusinessRejection(f"下書き {draft_id} は「{current.status.label}」なので「{target.label}」にできません")
        return self.find(draft_id)

    def record_approval(self, draft_id: int, at: datetime) -> Draft:
        return self._transition(draft_id, (S.PENDING,), S.APPROVED, approved_at=at.isoformat())

    def mark_sending(self, draft_id: int) -> Draft:
        return self._transition(draft_id, (S.APPROVED, S.FAILED), S.SENDING)

    def record_published(self, draft_id: int, post_id: str, at: datetime) -> Draft:
        return self._transition(draft_id, (S.SENDING,), S.PUBLISHED, post_id=post_id, published_at=at.isoformat())

    def record_failed(self, draft_id: int, error: str) -> Draft:
        return self._transition(draft_id, (S.SENDING,), S.FAILED, error=error)

    def discard(self, draft_id: int) -> Draft:
        return self._transition(draft_id, (S.PENDING, S.APPROVED, S.REJECTED), S.DISCARDED)
