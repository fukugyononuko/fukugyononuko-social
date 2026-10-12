"""CMP-A06 SettingsAccess の契約：単価表・為替と上限・禁止語（DD-12、EIF-03、EIF-04）。"""

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Protocol

from fukugyononuko_social.domain.channel import Channel
from fukugyononuko_social.domain.money import Budget


class SettingsAccess(Protocol):
    def price_table(self) -> Mapping[tuple[Channel, str], Decimal]: ...
    def budget(self) -> Budget: ...
    def denylist(self) -> Sequence[str]:
        """禁止語のファイルの行（注釈の行も含む）。読めなければ ExternalFailure。"""
        ...
