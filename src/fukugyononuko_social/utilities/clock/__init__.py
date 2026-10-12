"""CMP-U03 Clock の契約：現在時刻（UTC）を返す。テストでは固定した Clock を渡す。"""

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...
