"""CMP-E03 CostEngine の契約：費用の見積もりと、月の上限の判定（VOL-02、VOL-06、DD-08）。"""

from collections.abc import Sequence
from typing import Protocol

from fukugyononuko_social.domain.money import BudgetStatus, Cost, Usage


class CostEngine(Protocol):
    def estimate(self, usages: Sequence[Usage]) -> Cost: ...
    def afford(self, cost: Cost, month: str) -> bool: ...
    def status(self, month: str) -> BudgetStatus: ...
