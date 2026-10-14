"""CMP-A07 TransactionAccess の契約：保存先への複数の書き込みを、まとめて確定する（DD-21）。"""

from contextlib import AbstractContextManager
from typing import Protocol


class TransactionAccess(Protocol):
    def atomically(self) -> AbstractContextManager[None]:
        """with の中の書き込みは、すべて確定するか、どれも確定しない。入れ子にしない。"""
        ...
