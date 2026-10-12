"""GitHub Actions のワークフローが決まりを守っているかを検査する。

- 外部の Action はコミット SHA（40 桁）で固定する
- ワークフロー全体の既定の権限は contents: read だけ
- pull_request_target を使わない
"""

import re
import sys
from pathlib import Path

USES = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)")
PINNED = re.compile(r"@[0-9a-f]{40}$")


def check(path: Path) -> list[str]:
    problems = []
    lines = path.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines, start=1):
        m = USES.match(line)
        if m and not m[1].startswith("./") and not PINNED.search(m[1]):
            problems.append(f"{path}:{i} コミット SHA で固定されていない Action: {m[1]}")
        if re.match(r"^\s*pull_request_target\s*:?", line):
            problems.append(f"{path}:{i} pull_request_target は使わない")

    starts = [i for i, line in enumerate(lines) if re.fullmatch(r"permissions:\s*", line)]
    if not starts:
        return [*problems, f"{path}: ワークフロー全体の permissions がない"]
    block = []
    for line in lines[starts[0] + 1 :]:
        if not re.match(r"^\s+\S", line):
            break
        block.append(line.strip())
    if block != ["contents: read"]:
        actual = ", ".join(block) or "なし"
        problems.append(f"{path}: ワークフロー全体の permissions は contents: read だけにする（実際: {actual}）")
    return problems


def main() -> int:
    problems = [p for f in sorted(Path(".github/workflows").glob("*.y*ml")) for p in check(f)]
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    print("check_workflows: 問題はありません")
    return 0


if __name__ == "__main__":
    sys.exit(main())
