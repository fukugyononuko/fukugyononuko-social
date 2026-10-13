"""テスト用の偽物（ResourceAccess・Utility）。"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from fukugyononuko_social.domain.channel import Channel, month_of
from fukugyononuko_social.domain.drafts import PublishedPost
from fukugyononuko_social.domain.errors import ExternalFailure, Outcome, UncertainPost
from fukugyononuko_social.domain.metrics import (
    AccountSnapshot,
    Finished,
    MeasurementRun,
    MetricsHistory,
    PartialFetch,
    PostMetrics,
    Report,
    Running,
)
from fukugyononuko_social.domain.money import Budget, Cost, Usage

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
    links: list[tuple[int | None, int | None]] = field(default_factory=list)

    def record_charge(self, at: datetime, cost: Cost, *, run_id: int | None = None, draft_id: int | None = None) -> None:
        self.charges.append((at, cost))
        self.links.append((run_id, draft_id))

    def month_total_jpy(self, month: str) -> int:
        return sum(c.jpy for at, c in self.charges if month_of(at) == month)

    def totals_by_month_and_channel(self) -> Mapping[tuple[str, Channel], int]:
        totals: dict[tuple[str, Channel], int] = {}
        for at, c in self.charges:
            key = (month_of(at), c.usages[0].channel if c.usages else self.channel)
            totals[key] = totals.get(key, 0) + c.jpy
        return totals


@dataclass
class FakeMetrics:
    accounts: list[AccountSnapshot] = field(default_factory=list)
    posts: list[PostMetrics] = field(default_factory=list)
    last_run: MeasurementRun | None = None
    runs: int = 0

    def start_run(self, at: datetime) -> int:
        self.runs += 1
        self.last_run = Running(self.runs, at)
        return self.runs

    def finish_run(self, run_id: int, at: datetime, outcome: Outcome) -> None:
        self.last_run = Finished(run_id, at, at, outcome)

    def record(self, run_id: int, accounts: Sequence[AccountSnapshot], posts: Sequence[PostMetrics]) -> None:
        self.accounts += accounts
        self.posts += posts

    def history(self) -> MetricsHistory:
        return MetricsHistory(accounts=tuple(self.accounts), posts=tuple(self.posts), last_run=self.last_run)


@dataclass
class FakeChannel:
    """ChannelAccess の偽物。fail に "account"・"posts"・"post"・"uncertain" を入れると、その操作で失敗する。"""

    channel: Channel = Channel.X
    followers: int = 26
    post_ids: tuple[str, ...] = ("1", "2")
    fail: set[str] = field(default_factory=set)
    calls: list[str] = field(default_factory=list)
    sent: list[tuple[str, str]] = field(default_factory=list)

    def account_snapshot(self, at: datetime) -> tuple[AccountSnapshot, tuple[Usage, ...]]:
        self.calls.append("account")
        if "account" in self.fail:
            raise ExternalFailure("アカウントの取得に失敗")
        return AccountSnapshot(self.channel, at, self.followers, 26, len(self.post_ids)), (Usage(self.channel, "user_read", 1),)

    def recent_post_metrics(self, since: datetime, at: datetime) -> tuple[tuple[PostMetrics, ...], tuple[Usage, ...]]:
        self.calls.append("posts")
        posts = tuple(PostMetrics(self.channel, i, at, at, f"投稿 {i}", impressions=10) for i in self.post_ids)
        if "posts" in self.fail:
            raise PartialFetch("2 ページ目で失敗", usages=(Usage(self.channel, "post_read", 1),), posts=posts[:1])
        return posts, (Usage(self.channel, "post_read", len(posts)),)

    def post(self, text: str, operation: str) -> PublishedPost:
        self.calls.append("post")
        if "uncertain" in self.fail:
            raise UncertainPost("応答がない")
        if "post" in self.fail:
            raise ExternalFailure("投稿に失敗（403）")
        self.sent.append((text, operation))
        return PublishedPost(self.channel, f"p{len(self.sent)}", (Usage(self.channel, operation, 1),))

    def usage_upper_bound(self) -> tuple[Usage, ...]:
        return (Usage(self.channel, "user_read", 1), Usage(self.channel, "post_read", 100))


@dataclass
class FakeReport:
    published: list[Report] = field(default_factory=list)

    def publish_report(self, report: Report) -> None:
        self.published.append(report)


@dataclass
class FakeLog:
    lines: list[tuple[str, Outcome, dict[str, int | str]]] = field(default_factory=list)

    def record(self, command: str, outcome: Outcome, **detail: int | str) -> None:
        self.lines.append((command, outcome, detail))

    def recent(self, n: int) -> Sequence[str]:
        return [f"{c} {o.value}" for c, o, _ in self.lines[-n:]]
