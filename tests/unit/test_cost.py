"""TC-U04・U05：CMP-E03 CostEngine（DD-08）。TC-R03：単価表と為替をコードを変えずに差し替えられる。"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from fukugyononuko_social.contracts import Channel, Usage, UsageError
from fukugyononuko_social.engines.cost import DefaultCostEngine
from tests.fakes import FakeLedger, FakeSettings

MONTH = "2026-10"
AT = datetime(2026, 10, 12, 3, tzinfo=UTC)


def test_estimate_rounds_up_to_yen() -> None:
    engine = DefaultCostEngine(FakeSettings(), FakeLedger())
    cost = engine.estimate([Usage(Channel.X, "post_create", 1)])  # $0.015 × 170 = 2.55 円
    assert cost.usd == Decimal("0.015")
    assert cost.jpy == 3


def test_estimate_sums_usages() -> None:
    engine = DefaultCostEngine(FakeSettings(), FakeLedger())
    cost = engine.estimate([Usage(Channel.X, "user_read", 1), Usage(Channel.X, "post_read", 100)])
    assert cost.usd == Decimal("0.510")
    assert cost.jpy == 87  # 86.7 を切り上げ


def test_unknown_operation_is_usage_error() -> None:
    with pytest.raises(UsageError):
        DefaultCostEngine(FakeSettings(), FakeLedger()).estimate([Usage(Channel.X, "unknown", 1)])


def test_afford_boundary() -> None:
    ledger = FakeLedger()
    engine = DefaultCostEngine(FakeSettings(cap_jpy=10), ledger)
    ledger.record_charge(AT, engine.estimate([Usage(Channel.X, "post_create", 2)]))  # 6 円
    four = engine.estimate([Usage(Channel.X, "post_read", 4)])  # $0.02 × 170 = 3.4 → 4 円
    assert four.jpy == 4
    assert engine.afford(four, MONTH)  # 6 + 4 = 10 ちょうどは許す
    five = engine.estimate([Usage(Channel.X, "post_read", 5)])  # 4.25 → 5 円
    assert not engine.afford(five, MONTH)  # 11 は拒否


def test_status() -> None:
    ledger = FakeLedger()
    engine = DefaultCostEngine(FakeSettings(), ledger)
    ledger.record_charge(AT, engine.estimate([Usage(Channel.X, "post_create_with_url", 1)]))  # 34 円
    status = engine.status(MONTH)
    assert (status.spent_jpy, status.cap_jpy, status.remaining_jpy) == (34, 500, 466)


def test_r03_prices_and_rate_are_settings() -> None:
    settings = FakeSettings(usd_jpy=Decimal(100))
    settings.prices[(Channel.X, "post_create")] = Decimal("0.030")
    assert DefaultCostEngine(settings, FakeLedger()).estimate([Usage(Channel.X, "post_create", 1)]).jpy == 3
