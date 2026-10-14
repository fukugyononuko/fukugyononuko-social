"""CMP-A07 TransactionAccess の実装：SQLite（DD-21）。A02〜A04 と同じ接続を渡す。"""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager


class SqliteTransactionAccess:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    @contextmanager
    def atomically(self) -> Generator[None]:
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            if self._conn.in_transaction:  # 取り消しの失敗で、元の例外を隠さない
                self._conn.execute("ROLLBACK")
            raise
        self._conn.execute("COMMIT")
