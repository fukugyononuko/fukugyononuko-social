"""CMP-E01 AggregationEngine：時系列の数字から、月ごとの集計と直近の投稿の一覧を作る（DD-10）。"""

from collections import defaultdict
from datetime import datetime, timedelta

from fukugyononuko_social.contracts import (
    AccountSnapshot,
    Channel,
    LedgerAccess,
    MetricsAccess,
    MonthlyRow,
    PostMetrics,
    Report,
    month_of,
)

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

        keys = sorted(set(sums) | set(accounts) | set(costs), key=lambda k: (k[0], k[1].value))
        monthly = tuple(
            MonthlyRow(
                month=month,
                channel=channel,
                followers=accounts[(month, channel)].followers if (month, channel) in accounts else None,
                following=accounts[(month, channel)].following if (month, channel) in accounts else None,
                posts_created=sums.get((month, channel), {}).get("posts", 0),
                impressions=sums.get((month, channel), {}).get("impressions", 0),
                likes=sums.get((month, channel), {}).get("likes", 0),
                profile_clicks=sums.get((month, channel), {}).get("profile_clicks", 0),
                link_clicks=sums.get((month, channel), {}).get("link_clicks", 0),
                cost_jpy=costs.get((month, channel), 0),
            )
            for month, channel in keys
        )

        cutoff = now - timedelta(days=RECENT_DAYS)
        # 同じ表示回数どうしは、チャネルと投稿 ID の順にして並びを一意にする（開発の決まり：並び順の一意性）
        recent = tuple(
            sorted(
                (p for p in posts if p.created_at >= cutoff),
                key=lambda p: (-(p.impressions or 0), p.channel.value, p.post_id),
            )
        )
        return Report(generated_at=now, monthly=monthly, recent_posts=recent, last_run=history.last_run)
