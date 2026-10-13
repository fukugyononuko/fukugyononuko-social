"""CMP-U02 Logging の契約：実行の記録を 1 件残す／最後の数件を読む（DD-14、DD-15）。"""

from collections.abc import Sequence
from typing import Protocol

from fukugyononuko_social.domain.errors import Outcome


class Logging(Protocol):
    def record(self, command: str, outcome: Outcome, **detail: int | str) -> None: ...
    def recent(self, n: int) -> Sequence[str]:
        """最後の n 件を、記録した形のまま返す（CLI-09）。"""
        ...
