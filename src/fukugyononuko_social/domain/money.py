"""費用（DD-08）。"""

from dataclasses import dataclass
from decimal import Decimal

from fukugyononuko_social.domain.channel import Channel


@dataclass(frozen=True, slots=True)
class Usage:
    """課金される操作。operation は単価表のキー。"""

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
