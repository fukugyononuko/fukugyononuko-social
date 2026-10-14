"""CMP-U02 Logging の実装：1 行 1 件の JSON（EIF-07）。

文章の全文と認証情報は書かない。値は整数か短い文字列だけを受け付ける。
"""

import json
from collections import deque
from collections.abc import Sequence
from pathlib import Path

from fukugyononuko_social.domain.errors import Outcome
from fukugyononuko_social.domain.secret import Secret
from fukugyononuko_social.utilities.clock import Clock

MAX_TEXT = 200


class JsonLinesLog:
    def __init__(self, path: Path, clock: Clock) -> None:
        self._path = path
        self._clock = clock

    def record(self, command: str, outcome: Outcome, **detail: int | str) -> None:
        for key, value in detail.items():
            if isinstance(value, Secret):
                raise TypeError(f"ログに認証情報は書けません：{key}")
            if isinstance(value, str) and len(value) > MAX_TEXT:
                raise ValueError(f"ログの値が長すぎます（文章の全文は書かない）：{key}")
        line = {
            "at": self._clock.now().isoformat(timespec="seconds"),
            "command": command,
            "outcome": outcome.value,
            "detail": detail,
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False, sort_keys=True) + "\n")

    def recent(self, n: int) -> Sequence[str]:
        if not self._path.exists():
            return []
        with self._path.open(encoding="utf-8") as f:
            return [line.rstrip("\n") for line in deque(f, maxlen=max(n, 0))]
