"""層をまたぐ型・例外・契約（DD-02）。どの層も import してよい。標準ライブラリ以外に依存しない。"""

from __future__ import annotations

import hashlib
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import NoReturn, Protocol
from zoneinfo import ZoneInfo

# 月の区切りは運営者の暮らす時間帯で数える（DD-08、DD-10）
OPERATOR_TZ = ZoneInfo("Asia/Tokyo")


def month_of(moment: datetime) -> str:
    """UTC の時刻を、運営者の時間帯での「YYYY-MM」にする。"""
    return moment.astimezone(OPERATOR_TZ).strftime("%Y-%m")


# ---- 例外（DD-18） ----


class BusinessRejection(Exception):
    """検査の不合格、上限の超過、承認なし、指紋の不一致、許されない遷移。終了コード 1。"""


class UsageError(Exception):
    """引数の誤り、設定ファイルがない。終了コード 2。"""


class ExternalFailure(Exception):
    """API・キーチェーン・保存先の失敗。終了コード 3。"""


# ---- 値 ----


class Channel(StrEnum):
    X = "x"


class DraftStatus(StrEnum):
    REJECTED = "不合格"
    PENDING = "下書き"
    APPROVED = "承認済み"
    SENDING = "送信中"
    PUBLISHED = "投稿済み"
    FAILED = "失敗"
    DISCARDED = "破棄"


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


class Secret:
    """認証情報を包む。文字列にしても値が出ない（DD-13）。値は reveal() でだけ取り出す。"""

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        self._value = value

    def reveal(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return "Secret(***)"

    __str__ = __repr__

    def __format__(self, spec: str) -> str:
        return repr(self)

    def __reduce__(self) -> NoReturn:
        raise TypeError("Secret は保存・複製できません")


@dataclass(frozen=True, slots=True)
class Usage:
    """課金される操作。operation は単価表のキー（DD-08）。"""

    channel: Channel
    operation: str
    units: int


@dataclass(frozen=True, slots=True)
class Cost:
    usd: Decimal
    jpy: int
    usages: tuple[Usage, ...]


@dataclass(frozen=True, slots=True)
class Budget:
    monthly_cap_jpy: int
    usd_jpy: Decimal


@dataclass(frozen=True, slots=True)
class BudgetStatus:
    month: str
    spent_jpy: int
    cap_jpy: int

    @property
    def remaining_jpy(self) -> int:
        return self.cap_jpy - self.spent_jpy


@dataclass(frozen=True, slots=True)
class Finding:
    severity: Severity
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class AccountSnapshot:
    channel: Channel
    fetched_at: datetime
    followers: int
    following: int
    posts: int


@dataclass(frozen=True, slots=True)
class PostMetrics:
    """投稿ごとの数字。共通の項目名（02b §2b.3）。取れない項目は None。"""

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
class MeasurementRun:
    id: int
    started_at: datetime
    finished_at: datetime | None
    outcome: str | None


@dataclass(frozen=True, slots=True)
class MetricsHistory:
    accounts: tuple[AccountSnapshot, ...]
    posts: tuple[PostMetrics, ...]
    last_run: MeasurementRun | None


@dataclass(frozen=True, slots=True)
class MonthlyRow:
    month: str
    channel: Channel
    followers: int | None
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
class Draft:
    id: int
    channel: Channel
    text: str
    fingerprint: str
    status: DraftStatus
    findings: tuple[Finding, ...]
    estimate: Cost
    created_at: datetime
    approved_at: datetime | None = None
    post_id: str | None = None
    published_at: datetime | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class PublishedPost:
    channel: Channel
    post_id: str
    usages: tuple[Usage, ...] = field(default=())


def fingerprint(channel: Channel, text: str) -> str:
    """下書きの指紋（DD-05）。SHA-256 の 16 進 64 桁。表示は先頭 8 桁。"""
    normalized = unicodedata.normalize("NFC", text)
    return hashlib.sha256(f"{channel.value}\n{normalized}".encode()).hexdigest()


# ---- 契約（02b §2b.1）。具体的な実装は composition.py だけが知る（DD-15） ----


class Clock(Protocol):  # CMP-U03
    def now(self) -> datetime: ...


class Security(Protocol):  # CMP-U01
    def credential(self, channel: Channel, name: str) -> Secret: ...


class Logging(Protocol):  # CMP-U02
    def record(self, command: str, outcome: str, **detail: int | str) -> None: ...


class SettingsAccess(Protocol):  # CMP-A06
    def price_table(self) -> Mapping[tuple[Channel, str], Decimal]: ...
    def budget(self) -> Budget: ...
    def denylist(self) -> Sequence[str]: ...


class LedgerAccess(Protocol):  # CMP-A04
    def record_charge(self, at: datetime, cost: Cost, *, run_id: int | None = None, draft_id: int | None = None) -> None: ...
    def month_total_jpy(self, month: str) -> int: ...
    def totals_by_month_and_channel(self) -> Mapping[tuple[str, Channel], int]: ...


class MetricsAccess(Protocol):  # CMP-A02
    def start_run(self, at: datetime) -> int: ...
    def finish_run(self, run_id: int, at: datetime, outcome: str) -> None: ...
    def record(self, run_id: int, accounts: Sequence[AccountSnapshot], posts: Sequence[PostMetrics]) -> None: ...
    def history(self) -> MetricsHistory: ...


class DraftAccess(Protocol):  # CMP-A03
    def save_draft(
        self, channel: Channel, text: str, status: DraftStatus, findings: Sequence[Finding], estimate: Cost, at: datetime
    ) -> Draft: ...
    def find(self, draft_id: int) -> Draft: ...
    def list(self, status: DraftStatus | None = None) -> Sequence[Draft]: ...
    def record_approval(self, draft_id: int, at: datetime) -> None: ...
    def mark_sending(self, draft_id: int) -> None: ...
    def record_published(self, draft_id: int, post_id: str, at: datetime) -> None: ...
    def record_failed(self, draft_id: int, error: str) -> None: ...
    def discard(self, draft_id: int) -> None: ...


class ReportAccess(Protocol):  # CMP-A05
    def publish_report(self, report: Report) -> None: ...


class ChannelAccess(Protocol):  # CMP-A01
    channel: Channel

    def account_snapshot(self, at: datetime) -> tuple[AccountSnapshot, tuple[Usage, ...]]: ...
    def recent_post_metrics(self, since: datetime, at: datetime) -> tuple[tuple[PostMetrics, ...], tuple[Usage, ...]]: ...
    def post(self, text: str, operation: str) -> PublishedPost: ...
    def usage_upper_bound(self) -> tuple[Usage, ...]: ...


class AggregationEngine(Protocol):  # CMP-E01
    def summarize(self, now: datetime) -> Report: ...


class DraftPolicyEngine(Protocol):  # CMP-E02
    def review(self, channel: Channel, text: str) -> tuple[Finding, ...]: ...


class CostEngine(Protocol):  # CMP-E03
    def estimate(self, usages: Sequence[Usage]) -> Cost: ...
    def afford(self, cost: Cost, month: str) -> bool: ...
    def status(self, month: str) -> BudgetStatus: ...
