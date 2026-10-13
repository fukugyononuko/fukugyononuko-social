"""TC-U10・U13：保存先（SQLite）。状態の遷移と、表ごとの可変性（DD-03、DD-04）。"""

import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from fukugyononuko_social.access._sqlite import connect
from fukugyononuko_social.access.drafts.sqlite import SqliteDraftAccess
from fukugyononuko_social.access.ledger.sqlite import SqliteLedgerAccess
from fukugyononuko_social.access.metrics.sqlite import SqliteMetricsAccess
from fukugyononuko_social.domain.channel import Channel
from fukugyononuko_social.domain.drafts import (
    Approved,
    Discarded,
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
    fingerprint,
)
from fukugyononuko_social.domain.errors import BusinessRejection, Outcome
from fukugyononuko_social.domain.metrics import AccountSnapshot, Finished, PostMetrics, Running
from fukugyononuko_social.domain.money import Cost, Usage

AT = datetime(2026, 10, 13, 0, tzinfo=UTC)
COST = Cost(Decimal("0.015"), 3, (Usage(Channel.X, "post_create", 1),))
WARN = Finding(Severity.WARNING, "url", "URL を含みます")


@pytest.fixture
def conn() -> sqlite3.Connection:
    return connect(":memory:")


def test_schema_is_created_once(tmp_path) -> None:
    path = tmp_path / "data" / "nukosns.sqlite"
    connect(path).close()
    connect(path).close()
    assert path.exists()


# ---- 下書き（TC-U10） ----


def test_save_pass_and_fail(conn: sqlite3.Connection) -> None:
    drafts = SqliteDraftAccess(conn)
    ok = drafts.save_draft(Channel.X, "本文", Pass((WARN,)), COST, AT)
    assert ok.state == Pending() and ok.warnings == (WARN,) and ok.estimate == COST
    assert ok.fingerprint == fingerprint(Channel.X, "本文")
    error = Finding(Severity.ERROR, "length", "長すぎます")
    ng = drafts.save_draft(Channel.X, "本文", Fail((error,)), COST, AT)
    assert ng.state == Rejected((error,))


def test_happy_path_transitions(conn: sqlite3.Connection) -> None:
    drafts = SqliteDraftAccess(conn)
    d = drafts.save_draft(Channel.X, "本文", Pass(), COST, AT)
    assert drafts.record_approval(d.id, AT).state == Approved(AT)
    assert drafts.mark_sending(d.id).state == Sending(AT)
    later = AT + timedelta(seconds=5)
    assert drafts.record_published(d.id, "999", later).state == Published(AT, "999", later)


def test_failed_can_be_resent(conn: sqlite3.Connection) -> None:
    drafts = SqliteDraftAccess(conn)
    d = drafts.save_draft(Channel.X, "本文", Pass(), COST, AT)
    drafts.record_approval(d.id, AT)
    drafts.mark_sending(d.id)
    assert drafts.record_failed(d.id, "503").state == Failed(AT, "503")
    assert drafts.mark_sending(d.id).state == Sending(AT)


@pytest.mark.parametrize(
    ("setup", "action"),
    [
        ([], "mark_sending"),  # 承認なしで送信中にできない
        ([], "record_published"),
        (["record_approval"], "record_approval"),  # 二重の承認
        (["record_approval", "mark_sending"], "mark_sending"),  # 送信中を二重にできない（NFR-06）
        (["record_approval", "mark_sending"], "discard"),  # 送信中は破棄できない
        (["discard"], "record_approval"),
    ],
)
def test_illegal_transitions_are_rejected(conn: sqlite3.Connection, setup: list[str], action: str) -> None:
    drafts = SqliteDraftAccess(conn)
    d = drafts.save_draft(Channel.X, "本文", Pass(), COST, AT)
    calls = {
        "record_approval": lambda: drafts.record_approval(d.id, AT),
        "mark_sending": lambda: drafts.mark_sending(d.id),
        "record_published": lambda: drafts.record_published(d.id, "1", AT),
        "discard": lambda: drafts.discard(d.id),
    }
    for step in setup:
        calls[step]()
    with pytest.raises(BusinessRejection):
        calls[action]()


def test_rejected_can_only_be_discarded(conn: sqlite3.Connection) -> None:
    drafts = SqliteDraftAccess(conn)
    d = drafts.save_draft(Channel.X, "本文", Fail((Finding(Severity.ERROR, "e", "e"),)), COST, AT)
    with pytest.raises(BusinessRejection):
        drafts.record_approval(d.id, AT)
    assert drafts.discard(d.id).state == Discarded()


def test_list_by_status_and_missing_draft(conn: sqlite3.Connection) -> None:
    drafts = SqliteDraftAccess(conn)
    a = drafts.save_draft(Channel.X, "a", Pass(), COST, AT)
    drafts.save_draft(Channel.X, "b", Pass(), COST, AT)
    drafts.record_approval(a.id, AT)
    assert [d.text for d in drafts.drafts(DraftStatus.APPROVED)] == ["a"]
    assert len(drafts.drafts()) == 2
    with pytest.raises(BusinessRejection):
        drafts.find(99)


# ---- 可変性（TC-U13） ----


def test_draft_text_and_fingerprint_cannot_change(conn: sqlite3.Connection) -> None:
    d = SqliteDraftAccess(conn).save_draft(Channel.X, "本文", Pass(), COST, AT)
    for sql in ("UPDATE drafts SET text = 'x' WHERE id = ?", "UPDATE drafts SET fingerprint = 'x' WHERE id = ?"):
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(sql, (d.id,))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM drafts WHERE id = ?", (d.id,))


def test_immutable_tables_reject_update_and_delete(conn: sqlite3.Connection) -> None:
    metrics = SqliteMetricsAccess(conn)
    run = metrics.start_run(AT)
    metrics.record(run, [AccountSnapshot(Channel.X, AT, 1, 1, 1)], [PostMetrics(Channel.X, "1", AT, AT, "本文", impressions=1)])
    SqliteLedgerAccess(conn).record_charge(AT, COST, run_id=run)
    for table in ("account_snapshots", "post_metrics", "charges"):
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(f"UPDATE {table} SET channel = 'y'")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(f"DELETE FROM {table}")


def test_same_primary_key_is_not_duplicated(conn: sqlite3.Connection) -> None:
    metrics = SqliteMetricsAccess(conn)
    run = metrics.start_run(AT)
    snapshot = AccountSnapshot(Channel.X, AT, 1, 1, 1)
    post = PostMetrics(Channel.X, "1", AT, AT, "本文", impressions=1)
    metrics.record(run, [snapshot], [post])
    metrics.record(run, [snapshot], [post])
    history = metrics.history()
    assert len(history.accounts) == 1 and len(history.posts) == 1


def test_run_finishes_once(conn: sqlite3.Connection) -> None:
    metrics = SqliteMetricsAccess(conn)
    run = metrics.start_run(AT)
    assert metrics.history().last_run == Running(run, AT)
    metrics.finish_run(run, AT, Outcome.OK)
    assert metrics.history().last_run == Finished(run, AT, AT, Outcome.OK)
    with pytest.raises(sqlite3.IntegrityError):
        metrics.finish_run(run, AT, Outcome.FAILED)


def test_metrics_round_trip_keeps_none(conn: sqlite3.Connection) -> None:
    metrics = SqliteMetricsAccess(conn)
    run = metrics.start_run(AT)
    post = PostMetrics(Channel.X, "1", AT, AT, "本文", impressions=5, profile_clicks=None)
    metrics.record(run, [], [post])
    assert metrics.history().posts == (post,)


# ---- 費用 ----


def test_ledger_totals_by_operator_month(conn: sqlite3.Connection) -> None:
    ledger = SqliteLedgerAccess(conn)
    run = SqliteMetricsAccess(conn).start_run(AT)
    ledger.record_charge(datetime(2026, 9, 30, 15, tzinfo=UTC), COST, run_id=run)  # 日本時間で 10 月 1 日
    ledger.record_charge(datetime(2026, 9, 30, 14, tzinfo=UTC), COST, run_id=run)  # 日本時間で 9 月 30 日
    assert ledger.month_total_jpy("2026-10") == 3
    assert ledger.month_total_jpy("2026-09") == 3
    assert ledger.totals_by_month_and_channel() == {("2026-10", Channel.X): 3, ("2026-09", Channel.X): 3}


def test_ledger_needs_exactly_one_origin(conn: sqlite3.Connection) -> None:
    ledger = SqliteLedgerAccess(conn)
    with pytest.raises(ValueError):
        ledger.record_charge(AT, COST)
    with pytest.raises(ValueError):
        ledger.record_charge(AT, COST, run_id=1, draft_id=1)
