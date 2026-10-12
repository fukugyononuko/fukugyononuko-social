"""TC-U06：CMP-E01 AggregationEngine（DD-10、NFR-05）。"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fukugyononuko_social.contracts import AccountSnapshot, Channel, Cost, PostMetrics
from fukugyononuko_social.engines.aggregation import DefaultAggregationEngine
from tests.fakes import FakeLedger, FakeMetrics

NOW = datetime(2026, 10, 31, 0, tzinfo=UTC)


def post(post_id: str, created: datetime, fetched: datetime, impressions: int) -> PostMetrics:
    return PostMetrics(Channel.X, post_id, created, fetched, f"本文{post_id}", impressions=impressions, likes=1, profile_clicks=2)


def test_refetch_does_not_double_count() -> None:
    created = datetime(2026, 10, 10, tzinfo=UTC)
    metrics = FakeMetrics(
        posts=[post("1", created, created + timedelta(days=1), 10), post("1", created, created + timedelta(days=8), 30)]
    )
    report = DefaultAggregationEngine(metrics, FakeLedger()).summarize(NOW)
    [row] = report.monthly
    assert (row.posts_created, row.impressions, row.likes, row.profile_clicks) == (1, 30, 1, 2)


def test_account_uses_last_snapshot_of_month() -> None:
    metrics = FakeMetrics(
        accounts=[
            AccountSnapshot(Channel.X, datetime(2026, 10, 5, tzinfo=UTC), 20, 20, 3),
            AccountSnapshot(Channel.X, datetime(2026, 10, 26, tzinfo=UTC), 31, 25, 9),
            AccountSnapshot(Channel.X, datetime(2026, 10, 12, tzinfo=UTC), 26, 26, 5),
        ]
    )
    [row] = DefaultAggregationEngine(metrics, FakeLedger()).summarize(NOW).monthly
    assert (row.followers, row.following) == (31, 25)


def test_month_boundary_is_operator_timezone() -> None:
    # UTC で 9 月 30 日 15:00 は、日本時間で 10 月 1 日 0:00
    created = datetime(2026, 9, 30, 15, tzinfo=UTC)
    metrics = FakeMetrics(posts=[post("1", created, created, 5)])
    [row] = DefaultAggregationEngine(metrics, FakeLedger()).summarize(NOW).monthly
    assert row.month == "2026-10"


def test_cost_per_month() -> None:
    ledger = FakeLedger()
    ledger.record_charge(datetime(2026, 10, 5, tzinfo=UTC), Cost(usd=Decimal(0), jpy=7, usages=()))
    ledger.record_charge(datetime(2026, 10, 12, tzinfo=UTC), Cost(usd=Decimal(0), jpy=5, usages=()))
    [row] = DefaultAggregationEngine(FakeMetrics(), ledger).summarize(NOW).monthly
    assert row.cost_jpy == 12


def test_recent_posts_order_is_unique_and_window_is_29_days() -> None:
    fetched = NOW
    metrics = FakeMetrics(
        posts=[
            post("b", NOW - timedelta(days=1), fetched, 10),
            post("a", NOW - timedelta(days=2), fetched, 10),
            post("c", NOW - timedelta(days=3), fetched, 50),
            post("old", NOW - timedelta(days=30), fetched, 99),
        ]
    )
    recent = DefaultAggregationEngine(metrics, FakeLedger()).summarize(NOW).recent_posts
    assert [p.post_id for p in recent] == ["c", "a", "b"]
