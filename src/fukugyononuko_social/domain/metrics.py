"""計測の値（DD-02、DD-03、DD-10）。

計測 1 回分の状態は直和型（Running | Finished）で表し、「終わったのに結果がない」状態を作れないようにする。
投稿の数字の None は状態ではなく「そのチャネルでは取れない」というデータの欠けなので、Optional のままにする。
"""

from dataclasses import dataclass
from datetime import datetime

from fukugyononuko_social.domain.channel import Channel
from fukugyononuko_social.domain.errors import ExternalFailure, Outcome
from fukugyononuko_social.domain.money import Usage


@dataclass(frozen=True, slots=True)
class AccountSnapshot:
    channel: Channel
    fetched_at: datetime
    followers: int
    following: int
    posts: int


@dataclass(frozen=True, slots=True)
class PostMetrics:
    """投稿ごとの数字。共通の項目名（02b §2b.3）。"""

    channel: Channel
    post_id: str
    created_at: datetime
    fetched_at: datetime
    text_head: str
    impressions: int | None = None
    likes: int | None = None
    replies: int | None = None
    reposts: int | None = None
    quotes: int | None = None
    bookmarks: int | None = None
    profile_clicks: int | None = None
    link_clicks: int | None = None


@dataclass(frozen=True, slots=True)
class Running:
    id: int
    started_at: datetime


@dataclass(frozen=True, slots=True)
class Finished:
    id: int
    started_at: datetime
    finished_at: datetime
    outcome: Outcome


type MeasurementRun = Running | Finished


@dataclass(frozen=True, slots=True)
class MetricsHistory:
    accounts: tuple[AccountSnapshot, ...]
    posts: tuple[PostMetrics, ...]
    last_run: MeasurementRun | None


@dataclass(frozen=True, slots=True)
class MonthlyRow:
    month: str
    channel: Channel
    followers: int | None  # その月に一度も取れていなければ None
    following: int | None
    posts_created: int
    impressions: int
    likes: int
    profile_clicks: int
    link_clicks: int
    cost_jpy: int


@dataclass(frozen=True, slots=True)
class Report:
    generated_at: datetime
    monthly: tuple[MonthlyRow, ...]
    recent_posts: tuple[PostMetrics, ...]
    last_run: MeasurementRun | None


@dataclass(frozen=True, slots=True)
class MeasurementSummary:
    """計測 1 回分の結果（DD-19）。"""

    run_id: int
    accounts: int
    posts: int
    cost_jpy: int


class PartialFetch(ExternalFailure):
    """取得の途中の失敗（DD-09）。それまでに課金された操作と、取れた投稿を持つ。"""

    def __init__(self, message: str, *, usages: tuple[Usage, ...] = (), posts: tuple[PostMetrics, ...] = ()) -> None:
        super().__init__(message)
        self.usages = usages
        self.posts = posts
