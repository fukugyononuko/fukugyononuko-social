"""チャネルと、月の区切り。"""

from datetime import datetime
from enum import StrEnum
from zoneinfo import ZoneInfo

# 月の区切りは運営者の時間帯で数える（DD-08、DD-10）。保存する時刻は UTC のまま
OPERATOR_TZ = ZoneInfo("Asia/Tokyo")


class Channel(StrEnum):
    X = "x"


def month_of(moment: datetime) -> str:
    """UTC の時刻を、運営者の時間帯での「YYYY-MM」にする。"""
    return moment.astimezone(OPERATOR_TZ).strftime("%Y-%m")
