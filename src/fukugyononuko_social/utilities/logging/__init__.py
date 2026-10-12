"""CMP-U02 Logging の契約：実行の記録を 1 件残す（DD-14）。"""

from typing import Protocol

from fukugyononuko_social.domain.errors import Outcome


class Logging(Protocol):
    def record(self, command: str, outcome: Outcome, **detail: int | str) -> None: ...
