"""下書き（DD-02、DD-04、DD-05）。

検査の結果（Pass | Fail）と下書きの状態（Rejected | Pending | … | Discarded）を直和型で表す。
承認の時刻・投稿 ID・エラー文は、それを持つ状態にだけ置く。「下書きなのに投稿 ID がある」状態は型の上で作れない。
"""

import hashlib
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import assert_never

from fukugyononuko_social.domain.channel import Channel
from fukugyononuko_social.domain.money import Cost, Usage


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class Finding:
    severity: Severity
    code: str
    message: str


# ---- 検査の結果 ----


@dataclass(frozen=True, slots=True)
class Pass:
    warnings: tuple[Finding, ...] = ()


@dataclass(frozen=True, slots=True)
class Fail:
    errors: tuple[Finding, ...]  # 1 件以上
    warnings: tuple[Finding, ...] = ()

    def __post_init__(self) -> None:
        if not self.errors:
            raise ValueError("Fail には理由が 1 件以上必要です")


type Verdict = Pass | Fail


def verdict_of(findings: tuple[Finding, ...]) -> Verdict:
    errors = tuple(f for f in findings if f.severity is Severity.ERROR)
    warnings = tuple(f for f in findings if f.severity is Severity.WARNING)
    return Fail(errors, warnings) if errors else Pass(warnings)


# ---- 下書きの状態（02a §2a.1） ----


@dataclass(frozen=True, slots=True)
class Rejected:
    errors: tuple[Finding, ...]


@dataclass(frozen=True, slots=True)
class Pending:
    pass


@dataclass(frozen=True, slots=True)
class Approved:
    approved_at: datetime


@dataclass(frozen=True, slots=True)
class Sending:
    approved_at: datetime


@dataclass(frozen=True, slots=True)
class Published:
    approved_at: datetime
    post_id: str
    published_at: datetime


@dataclass(frozen=True, slots=True)
class Failed:
    approved_at: datetime
    error: str


@dataclass(frozen=True, slots=True)
class Discarded:
    pass


type DraftState = Rejected | Pending | Approved | Sending | Published | Failed | Discarded


class DraftStatus(StrEnum):
    """状態の名前。値は保存とコマンドの引数に使い、label は表示に使う。"""

    REJECTED = "rejected"
    PENDING = "pending"
    APPROVED = "approved"
    SENDING = "sending"
    PUBLISHED = "published"
    FAILED = "failed"
    DISCARDED = "discarded"

    @property
    def label(self) -> str:
        return _LABELS[self]


_LABELS = {
    DraftStatus.REJECTED: "不合格",
    DraftStatus.PENDING: "下書き",
    DraftStatus.APPROVED: "承認済み",
    DraftStatus.SENDING: "送信中",
    DraftStatus.PUBLISHED: "投稿済み",
    DraftStatus.FAILED: "失敗",
    DraftStatus.DISCARDED: "破棄",
}


def status_of(state: DraftState) -> DraftStatus:
    match state:
        case Rejected():
            return DraftStatus.REJECTED
        case Pending():
            return DraftStatus.PENDING
        case Approved():
            return DraftStatus.APPROVED
        case Sending():
            return DraftStatus.SENDING
        case Published():
            return DraftStatus.PUBLISHED
        case Failed():
            return DraftStatus.FAILED
        case Discarded():
            return DraftStatus.DISCARDED
        case _:
            assert_never(state)


@dataclass(frozen=True, slots=True)
class Draft:
    id: int
    channel: Channel
    text: str
    fingerprint: str
    warnings: tuple[Finding, ...]
    estimate: Cost
    created_at: datetime
    state: DraftState

    @property
    def status(self) -> DraftStatus:
        return status_of(self.state)


@dataclass(frozen=True, slots=True)
class PublishedPost:
    channel: Channel
    post_id: str
    usages: tuple[Usage, ...] = ()


def fingerprint(channel: Channel, text: str) -> str:
    """下書きの指紋（DD-05）。SHA-256 の 16 進 64 桁。表示は先頭 8 桁。"""
    normalized = unicodedata.normalize("NFC", text)
    return hashlib.sha256(f"{channel.value}\n{normalized}".encode()).hexdigest()
