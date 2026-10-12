"""CMP-E01 AggregationEngine の契約：月ごとの集計と直近の投稿の一覧を作る（VOL-04、DD-10）。"""

from datetime import datetime
from typing import Protocol

from fukugyononuko_social.domain.metrics import Report


class AggregationEngine(Protocol):
    def summarize(self, now: datetime) -> Report: ...
