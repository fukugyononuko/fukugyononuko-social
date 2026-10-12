"""CMP-A02 MetricsAccess の契約：取得した数字の時系列と、計測 1 回分の記録（DD-03）。"""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from fukugyononuko_social.domain.errors import Outcome
from fukugyononuko_social.domain.metrics import AccountSnapshot, MetricsHistory, PostMetrics


class MetricsAccess(Protocol):
    def start_run(self, at: datetime) -> int: ...
    def finish_run(self, run_id: int, at: datetime, outcome: Outcome) -> None: ...
    def record(self, run_id: int, accounts: Sequence[AccountSnapshot], posts: Sequence[PostMetrics]) -> None: ...
    def history(self) -> MetricsHistory: ...
