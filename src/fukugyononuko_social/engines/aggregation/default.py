"""CMP-E01 AggregationEngine の実装（DD-10）。"""

from collections import defaultdict
from datetime import datetime, timedelta

from fukugyononuko_social.access.ledger import LedgerAccess
from fukugyononuko_social.access.metrics import MetricsAccess
from fukugyononuko_social.domain.channel import Channel, month_of
from fukugyononuko_social.domain.metrics import AccountSnapshot, MonthlyRow, PostMetrics, Report

RECENT_DAYS = 29


def latest_per_post(posts: tuple[PostMetrics, ...]) -> list[PostMetrics]:
    """投稿ごとに、いちばん新しく取得した値だけを残す（NFR-05）。"""
    latest: dict[tuple[Channel, str], PostMetrics] = {}
    for p in posts:
        key = (p.channel, p.post_id)
        if key not in latest or p.fetched_at > latest[key].fetched_at:
            latest[key] = p
    return list(latest.values())


def last_account_per_month(accounts: tuple[AccountSnapshot, ...]) -> dict[tuple[str, Channel], AccountSnapshot]:
    last: dict[tuple[str, Channel], AccountSnapshot] = {}
    for a in accounts:
        key = (month_of(a.fetched_at), a.channel)
        if key not in last or a.fetched_at > last[key].fetched_at:
            last[key] = a
    return last


class DefaultAggregationEngine:
    def __init__(self, metrics: MetricsAccess, ledger: LedgerAccess) -> None:
        self._metrics = metrics
        self._ledger = ledger

    def summarize(self, now: datetime) -> Report:
        history = self._metrics.history()
        posts = latest_per_post(history.posts)
        accounts = last_account_per_month(history.accounts)
        costs = self._ledger.totals_by_month_and_channel()

        sums: dict[tuple[str, Channel], dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for p in posts:
            s = sums[(month_of(p.created_at), p.channel)]
            s["posts"] += 1
            s["impressions"] += p.impressions or 0
            s["likes"] += p.likes or 0
            s["profile_clicks"] += p.profile_clicks or 0
            s["link_clicks"] += p.link_clicks or 0

        def row(month: str, channel: Channel) -> MonthlyRow:
            s = sums.get((month, channel), {})
            a = accounts.get((month, channel))
            return MonthlyRow(
                month=month,
                channel=channel,
                followers=a.followers if a else None,
                following=a.following if a else None,
                posts_created=s.get("posts", 0),
                impressions=s.get("impressions", 0),
                likes=s.get("likes", 0),
                profile_clicks=s.get("profile_clicks", 0),
                link_clicks=s.get("link_clicks", 0),
                cost_jpy=costs.get((month, channel), 0),
            )

        keys = sorted(set(sums) | set(accounts) | set(costs), key=lambda k: (k[0], k[1].value))
        cutoff = now - timedelta(days=RECENT_DAYS)
        # 同じ表示回数どうしは、チャネルと投稿 ID の順にして並びを一意にする
        recent = sorted(
            (p for p in posts if p.created_at >= cutoff),
            key=lambda p: (-(p.impressions or 0), p.channel.value, p.post_id),
        )
        return Report(
            generated_at=now,
            monthly=tuple(row(m, c) for m, c in keys),
            recent_posts=tuple(recent),
            last_run=history.last_run,
        )
