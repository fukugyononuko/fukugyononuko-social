"""TC-I01〜I03、I08、I09、TC-R01、R02：CMP-M01 MeasurementManager と偽物の ResourceAccess（CC-01、CC-05、DD-19）。

保存先は、メモリ上の偽物（FakeMetrics・FakeLedger）に差し替えている（TC-R02）。
"""

from datetime import UTC, datetime

import pytest

from fukugyononuko_social.domain.errors import BusinessRejection, ExternalFailure, Outcome
from fukugyononuko_social.domain.metrics import Finished
from fukugyononuko_social.engines.aggregation.default import DefaultAggregationEngine
from fukugyononuko_social.engines.cost.default import DefaultCostEngine
from fukugyononuko_social.managers.measurement.default import DefaultMeasurementManager
from tests.fakes import FakeChannel, FakeLedger, FakeLog, FakeMetrics, FakeReport, FakeSettings, FixedClock

NOW = datetime(2026, 10, 19, 0, tzinfo=UTC)


class World:
    def __init__(self, *channels: FakeChannel, cap_jpy: int = 500) -> None:
        self.channels = channels or (FakeChannel(),)
        self.metrics = FakeMetrics()
        self.ledger = FakeLedger()
        self.report = FakeReport()
        self.log = FakeLog()
        self.settings = FakeSettings(cap_jpy=cap_jpy)
        cost = DefaultCostEngine(self.settings, self.ledger)
        self.manager = DefaultMeasurementManager(
            self.channels,
            self.metrics,
            self.ledger,
            self.report,
            DefaultAggregationEngine(self.metrics, self.ledger),
            cost,
            FixedClock(NOW),
            self.log,
        )

    def last_outcome(self) -> Outcome:
        run = self.metrics.last_run
        assert isinstance(run, Finished)
        return run.outcome


def test_i01_measure_fetches_saves_charges_and_reports() -> None:
    w = World()
    summary = w.manager.measure()
    assert (summary.accounts, summary.posts) == (1, 2)
    assert len(w.metrics.accounts) == 1 and len(w.metrics.posts) == 2
    # user_read 1 件 $0.010 + post_read 2 件 $0.010 = $0.020 → 4 円（切り上げ）
    assert summary.cost_jpy == 4
    assert [c.jpy for _, c in w.ledger.charges] == [4]
    assert w.ledger.links == [(summary.run_id, None)]
    assert len(w.report.published) == 1
    assert w.last_outcome() is Outcome.OK
    assert w.log.lines[-1][:2] == ("measure", Outcome.OK)


def test_i02_over_budget_stops_before_calling_api() -> None:
    w = World(cap_jpy=50)  # 上限の見積もり $0.51 → 87 円
    with pytest.raises(BusinessRejection):
        w.manager.measure()
    assert w.channels[0].calls == []
    assert w.ledger.charges == []
    assert w.report.published == []
    assert w.last_outcome() is Outcome.REJECTED
    assert w.log.lines[-1][:2] == ("measure", Outcome.REJECTED)


def test_i03_partial_failure_saves_what_was_fetched_and_keeps_report() -> None:
    w = World(FakeChannel(fail={"posts"}))
    with pytest.raises(ExternalFailure, match="集計は前回のまま"):
        w.manager.measure()
    assert len(w.metrics.accounts) == 1
    assert [p.post_id for p in w.metrics.posts] == ["1"]
    # 成功した分（user_read 1 件 + post_read 1 件 = $0.015 → 3 円）だけ記録する
    assert [c.jpy for _, c in w.ledger.charges] == [3]
    assert w.report.published == []
    assert w.last_outcome() is Outcome.FAILED
    assert w.log.lines[-1][:2] == ("measure", Outcome.FAILED)


def test_i08_cost_status_this_month() -> None:
    w = World()
    w.manager.measure()
    status = w.manager.cost_status()
    assert (status.month, status.spent_jpy, status.cap_jpy, status.remaining_jpy) == ("2026-10", 4, 500, 496)
    assert w.manager.cost_status("2026-09").spent_jpy == 0


def test_i09_one_channel_failing_does_not_stop_the_others() -> None:
    broken = FakeChannel(fail={"account"})
    healthy = FakeChannel(post_ids=("7",))
    w = World(broken, healthy)
    with pytest.raises(ExternalFailure, match="x："):
        w.manager.measure()
    assert healthy.calls == ["account", "posts"]
    assert [p.post_id for p in w.metrics.posts] == ["7"]
    assert len(w.ledger.charges) == 1  # 失敗したチャネルは課金されていない
    assert w.report.published == []
    assert w.last_outcome() is Outcome.FAILED


def test_r01_more_channel_accesses_need_no_manager_change() -> None:
    """チャネルの列挙が X だけのあいだは、2 つの ChannelAccess で確かめる（04 TC-R01）。"""
    w = World(FakeChannel(post_ids=("1",)), FakeChannel(post_ids=("2", "3")))
    summary = w.manager.measure()
    assert (summary.accounts, summary.posts) == (2, 3)
    assert len(w.ledger.charges) == 2  # 費用はチャネル（ChannelAccess）ごとに 1 件
    assert len(w.report.published) == 1


def test_r02_storage_is_replaceable_by_in_memory_fakes() -> None:
    """このファイルのテストはすべて、保存先をメモリ上の偽物にして Manager・Engine を変えずに動いている。"""
    w = World()
    w.manager.measure()
    w.manager.measure()
    report = w.report.published[-1]
    assert sum(r.impressions for r in report.monthly) == 20  # 2 回取っても投稿ごとに最新の値だけ（NFR-05）
