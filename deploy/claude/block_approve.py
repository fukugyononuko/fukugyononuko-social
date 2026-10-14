#!/usr/bin/env python3
"""Claude Code の PreToolUse hook：Claude が承認のコマンドを実行するのを止める（DD-17）。

標準入力の JSON の `tool_input.command` を調べ、1 つのコマンド（; & | 改行で区切った単位）の中に
`nukosns`（または `fukugyononuko_social.composition`）と、そのあとに単語 `approve` があれば、終了コード 2 で止める。
承認は、運営者が `!` を付けて自分で実行する。標準ライブラリだけで書き、どの python3 でも動くようにする。
"""

import json
import re
import sys

SEGMENT = re.compile(r"[;&|\n]")
TARGET = re.compile(r"(nukosns|fukugyononuko_social\.composition)\b")
APPROVE = re.compile(r"\bapprove\b")
MESSAGE = "承認（nukosns approve）は運営者だけが実行します。運営者に `! nukosns approve 番号 指紋` を打ってもらってください"


def blocked(command: str) -> bool:
    for segment in SEGMENT.split(command):
        found = TARGET.search(segment)
        if found and APPROVE.search(segment, found.end()):
            return True
    return False


def main() -> int:
    try:
        command = json.load(sys.stdin).get("tool_input", {}).get("command", "")
    except ValueError, AttributeError:
        return 0  # 読めない入力では、ほかのコマンドを止めない
    if isinstance(command, str) and blocked(command):
        print(MESSAGE, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
