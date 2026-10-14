"""週 1 回の計測を launchd に登録する（DD-16、EIF-08）。

使い方：uv run python scripts/install_launchd.py [--dry-run]
`nukosns` は先に `uv tool install --editable .` で入れておく。
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
LABEL = "com.fukugyononuko.nukosns.measure"
TEMPLATE = ROOT / "deploy" / "launchd" / f"{LABEL}.plist"
DEFAULT_HOME = "~/fukugyononuko/data/fukugyononuko-social"


def render(template: str, nukosns: Path, logs: Path) -> str:
    return template.replace("{NUKOSNS}", escape(str(nukosns))).replace("{LOGS}", escape(str(logs)))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="書き出す内容を表示するだけ")
    args = parser.parse_args()

    found = shutil.which("nukosns")
    if found is None:
        print("nukosns が見つかりません。先に `uv tool install --editable .` を実行してください", file=sys.stderr)
        return 2
    logs = Path(os.environ.get("NUKOSNS_HOME", DEFAULT_HOME)).expanduser() / "logs"
    plist = render(TEMPLATE.read_text(encoding="utf-8"), Path(found).resolve(), logs)
    if args.dry_run:
        print(plist)
        return 0

    logs.mkdir(parents=True, exist_ok=True)
    target = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
    target.write_text(plist, encoding="utf-8")
    domain = f"gui/{os.getuid()}"
    # 登録済みなら外してから入れ直す（初回は外すものがないので、失敗してよい）
    subprocess.run(["launchctl", "bootout", f"{domain}/{LABEL}"], capture_output=True, check=False)
    subprocess.run(["launchctl", "bootstrap", domain, str(target)], check=True)
    print(f"登録しました：{target}（毎週月曜 9:00 に nukosns measure）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
