"""CMP-M01 MeasurementManager の契約：UC-01（週次の計測）と UC-03（費用の確認）の流れ（CC-01、CC-05、DD-19）。"""

from typing import Protocol

from fukugyononuko_social.domain.metrics import MeasurementSummary
from fukugyononuko_social.domain.money import BudgetStatus


class MeasurementManager(Protocol):
    def measure(self) -> MeasurementSummary:
        """上限を超えるなら BusinessRejection、どれかのチャネルが失敗したら ExternalFailure。"""
        ...

    def cost_status(self, month: str | None = None) -> BudgetStatus:
        """その月（省略すると今月）の費用の合計・上限・残り。"""
        ...
