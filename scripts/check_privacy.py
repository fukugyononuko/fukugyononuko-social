"""個人情報が公開リポジトリに入っていないかを検査する（ホームページの TC-N06 と同じ決まり。NFR-03）。

1. コミットの作者・コミッターのアドレスが、許可したものだけであること
2. 公開される文章（追跡しているファイル、すべてのコミットメッセージ、PR のタイトルと本文）に禁止語がないこと
   禁止語は公開リポジトリに書かず、環境変数 PRIVACY_DENYLIST（GitHub の Secret）か、
   git 管理外のファイル .privacy-denylist から読む。どちらもなければ、この検査は飛ばして警告する。
"""

import os
import re
import subprocess
import sys
from pathlib import Path

ALLOWED_EMAILS = {
    "340638804+fukugyononuko@users.noreply.github.com",
    "fukugyononuko@gmail.com",
    "noreply@github.com",
    "49699333+dependabot[bot]@users.noreply.github.com",
}
TEXT_FILE = re.compile(r"\.(md|py|toml|ya?ml|txt|json|csv|cfg|ini|lock)$")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def main() -> int:
    problems = []
    identities = {e for e in git("log", "--format=%ae%n%ce").splitlines() if e}
    problems += [f"許可していないアドレスのコミットがあります：{e}" for e in sorted(identities - ALLOWED_EMAILS)]

    raw = os.environ.get("PRIVACY_DENYLIST") or (
        Path(".privacy-denylist").read_text(encoding="utf-8") if Path(".privacy-denylist").exists() else ""
    )
    denylist = [w.strip().lower() for w in raw.splitlines() if w.strip()]
    if not denylist:
        print("check_privacy: 禁止語が設定されていないため、文章の検査を飛ばしました（PRIVACY_DENYLIST か .privacy-denylist）")
    else:
        sources = [
            (f, Path(f).read_text(encoding="utf-8", errors="ignore")) for f in git("ls-files").splitlines() if TEXT_FILE.search(f)
        ]
        log = git("log", "--format=%H%x00%B%x00").split("\0")
        sources += [(f"コミット {log[i].strip()[:7]} のメッセージ", log[i + 1]) for i in range(0, len(log) - 1, 2)]
        if os.environ.get("PR_TEXT"):
            sources.append(("PR のタイトルと本文", os.environ["PR_TEXT"]))
        for where, text in sources:
            lowered = text.lower()
            # 禁止語そのものはログに出さない（CI のログも公開されるため）
            problems += [f"{where}：禁止語（{i + 1} 行目の語）が含まれています" for i, w in enumerate(denylist) if w in lowered]

    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    pr = "あり" if os.environ.get("PR_TEXT") else "なし"
    print(
        f"check_privacy: 問題はありません（コミットのアドレス {len(identities)} 種類、禁止語 {len(denylist)} 語、PR の本文 {pr}）"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
