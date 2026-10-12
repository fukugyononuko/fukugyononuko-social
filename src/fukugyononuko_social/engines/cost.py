"""CMP-E03 CostEngine：費用の見積もりと、月の上限の判定（DD-08）。"""

import math
from collections.abc import Sequence
from decimal import Decimal

from fukugyononuko_social.contracts import BudgetStatus, Cost, LedgerAccess, SettingsAccess, Usage, UsageError


class DefaultCostEngine:
    def __init__(self, settings: SettingsAccess, ledger: LedgerAccess) -> None:
        self._settings = settings
        self._ledger = ledger

    def estimate(self, usages: Sequence[Usage]) -> Cost:
        prices = self._settings.price_table()
        usd = Decimal(0)
        for u in usages:
            price = prices.get((u.channel, u.operation))
            if price is None:
                raise UsageError(f"単価表にない操作です：{u.channel.value}.{u.operation}")
            usd += price * u.units
        rate = self._settings.budget().usd_jpy
        return Cost(usd=usd, jpy=math.ceil(usd * rate), usages=tuple(usages))

    def afford(self, cost: Cost, month: str) -> bool:
        return self._ledger.month_total_jpy(month) + cost.jpy <= self._settings.budget().monthly_cap_jpy

    def status(self, month: str) -> BudgetStatus:
        return BudgetStatus(
            month=month, spent_jpy=self._ledger.month_total_jpy(month), cap_jpy=self._settings.budget().monthly_cap_jpy
        )
