"""CMP-U03 Clock：現在時刻（UTC）を返す。テストでは固定した Clock を渡す。"""

from datetime import UTC, datetime


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)
