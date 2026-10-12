"""テスト用の偽物（ResourceAccess・Utility）。"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from fukugyononuko_social.domain.channel import Channel, month_of
from fukugyononuko_social.domain.errors import ExternalFailure, Outcome
from fukugyononuko_social.domain.metrics import AccountSnapshot, Finished, MeasurementRun, MetricsHistory, PostMetrics
from fukugyononuko_social.domain.money import Budget, Cost

X_PRICES = {
    (Channel.X, "user_read"): Decimal("0.010"),
    (Channel.X, "post_read"): Decimal("0.005"),
    (Channel.X, "post_create"): Decimal("0.015"),
    (Channel.X, "post_create_with_url"): Decimal("0.200"),
}


@dataclass
class FixedClock:
    moment: datetime

    def now(self) -> datetime:
        return self.moment


@dataclass
class FakeSettings:
    prices: dict[tuple[Channel, str], Decimal] = field(default_factory=lambda: dict(X_PRICES))
    cap_jpy: int = 500
    usd_jpy: Decimal = Decimal(170)
    words: list[str] | None = field(default_factory=lambda: ["# 注釈", "禁止語いち", "Forbidden"])

    def price_table(self) -> Mapping[tuple[Channel, str], Decimal]:
        return self.prices

    def budget(self) -> Budget:
        return Budget(monthly_cap_jpy=self.cap_jpy, usd_jpy=self.usd_jpy)

    def denylist(self) -> Sequence[str]:
        if self.words is None:
            raise ExternalFailure("禁止語のファイルが読めません")
        return self.words


@dataclass
class FakeLedger:
    charges: list[tuple[datetime, Cost]] = field(default_factory=list)
    channel: Channel = Channel.X

    def record_charge(self, at: datetime, cost: Cost, *, run_id: int | None = None, draft_id: int | None = None) -> None:
        self.charges.append((at, cost))

    def month_total_jpy(self, month: str) -> int:
        return sum(c.jpy for at, c in self.charges if month_of(at) == month)

    def totals_by_month_and_channel(self) -> Mapping[tuple[str, Channel], int]:
        totals: dict[tuple[str, Channel], int] = {}
        for at, c in self.charges:
            key = (month_of(at), self.channel)
            totals[key] = totals.get(key, 0) + c.jpy
        return totals


@dataclass
class FakeMetrics:
    accounts: list[AccountSnapshot] = field(default_factory=list)
    posts: list[PostMetrics] = field(default_factory=list)
    last_run: MeasurementRun | None = None

    def start_run(self, at: datetime) -> int:
        return 1

    def finish_run(self, run_id: int, at: datetime, outcome: Outcome) -> None:
        self.last_run = Finished(run_id, at, at, outcome)

    def record(self, run_id: int, accounts: Sequence[AccountSnapshot], posts: Sequence[PostMetrics]) -> None:
        self.accounts += accounts
        self.posts += posts

    def history(self) -> MetricsHistory:
        return MetricsHistory(accounts=tuple(self.accounts), posts=tuple(self.posts), last_run=self.last_run)
