"""CMP-A04 LedgerAccess の契約：費用の記録と月ごとの合計（DD-03 charges、IMMUTABLE）。"""

from collections.abc import Mapping
from datetime import datetime
from typing import Protocol

from fukugyononuko_social.domain.channel import Channel
from fukugyononuko_social.domain.money import Cost


class LedgerAccess(Protocol):
    def record_charge(self, at: datetime, cost: Cost, *, run_id: int | None = None, draft_id: int | None = None) -> None: ...
    def month_total_jpy(self, month: str) -> int: ...
    def totals_by_month_and_channel(self) -> Mapping[tuple[str, Channel], int]: ...
