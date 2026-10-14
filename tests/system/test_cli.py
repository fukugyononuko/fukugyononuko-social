"""TC-S01〜S03、TC-N02：CLI を通した総合テスト（DD-15）。

本物の組み立て（SQLite・設定・書き出し・ログ）を一時フォルダで使い、チャネルだけ偽物にする（NFR-09）。
"""

import json
import re
from pathlib import Path

import pytest

from fukugyononuko_social import composition
from fukugyononuko_social.clients.cli.main import run
from tests.fakes import FakeChannel

SETTINGS = """
[budget]
monthly_cap_jpy = 500
usd_jpy = 170

[paths]
denylist = "{base}/denylist"
report = "{base}/vault/SNS.md"

[prices.x]
user_read = "0.010"
post_read = "0.005"
post_create = "0.015"
post_create_with_url = "0.200"
"""


@pytest.fixture
def base(tmp_path: Path) -> Path:
    (tmp_path / "settings.toml").write_text(SETTINGS.format(base=tmp_path), encoding="utf-8")
    (tmp_path / "denylist").write_text("# 注釈\n禁止語いち\n", encoding="utf-8")
    return tmp_path


class Cli:
    def __init__(self, base: Path, capsys: pytest.CaptureFixture[str], channel: FakeChannel | None = None) -> None:
        self.base = base
        self.capsys = capsys
        self.channel = channel or FakeChannel()

    def __call__(self, *argv: str) -> tuple[int, str, str]:
        code = run(list(argv), lambda: composition.build(self.base, channels=(self.channel,)))
        out, err = self.capsys.readouterr()
        return code, out, err


def test_s01_add_approve_publish(base: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cli = Cli(base, capsys)
    code, out, _ = cli("draft", "add", "--channel", "x", "--text", "はじめての投稿です")
    assert code == 0
    m = re.search(r"! nukosns approve (\d+) ([0-9a-f]{8})", out)
    assert m is not None
    draft_id, short = m.groups()

    assert cli("approve", draft_id, short)[0] == 0
    code, out, _ = cli("publish", draft_id)
    assert code == 0 and "投稿 ID：p1" in out
    assert cli.channel.sent == [("はじめての投稿です", "post_create")]
    code, out, _ = cli("draft", "list", "--status", "published")
    assert f"#{draft_id}\t投稿済み" in out
    code, out, _ = cli("cost")
    assert code == 0 and "使用 3 円 / 上限 500 円" in out


def test_s02_exit_codes(base: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cli = Cli(base, capsys, FakeChannel(fail={"post"}))
    # 1：業務上の拒否
    code, out, _ = cli("draft", "add", "--channel", "x", "--text", "禁止語いちを含む")
    assert code == 1 and "不合格の理由" in out and "禁止語いち" not in out.split("----")[0]
    code, _, err = cli("publish", "1")
    assert code == 1 and err.startswith("エラー：")
    # 2：使い方の誤り
    assert cli("draft", "show", "abc")[0] == 2
    assert cli("cost", "--month", "2026-13")[0] == 2
    assert cli("draft", "add", "--channel", "x", "--file", str(base / "ない.txt"))[0] == 2
    # 3：外部の失敗
    _, out, _ = cli("draft", "add", "--channel", "x", "--text", "ふつうの投稿")
    m = re.search(r"approve (\d+) ([0-9a-f]{8})", out)
    assert m is not None
    cli("approve", *m.groups())
    assert cli("publish", m.group(1))[0] == 3


def test_s02_missing_settings_is_usage_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = Cli(tmp_path, capsys)("draft", "list")
    assert code == 2 and "settings.example.toml" in err


def test_s03_measure_writes_and_replaces_report(base: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cli = Cli(base, capsys)
    code, out, _ = cli("measure")
    assert code == 0 and "投稿 2 件" in out
    report = base / "vault" / "SNS.md"
    first = report.read_text(encoding="utf-8")
    cli.channel.post_ids = ("1", "2", "3")
    assert cli("measure")[0] == 0
    second = report.read_text(encoding="utf-8")
    assert second != first and second.count("# ") == first.count("# ")  # 追記ではなく全体の置き換え
    assert "投稿 3" in second


def test_n02_log_has_no_text_or_secrets(base: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cli = Cli(base, capsys)
    secret_text = "ログに出してはいけない本文"
    _, out, _ = cli("draft", "add", "--channel", "x", "--text", secret_text)
    m = re.search(r"approve (\d+) ([0-9a-f]{8})", out)
    assert m is not None
    cli("approve", *m.groups())
    cli("publish", m.group(1))
    cli("measure")
    code, out, _ = cli("log", "--tail", "10")
    assert code == 0
    raw = (base / "logs" / "nukosns.log").read_text(encoding="utf-8")
    lines = [json.loads(line) for line in raw.splitlines()]
    assert [line["command"] for line in lines] == ["draft add", "approve", "publish", "measure"]
    assert secret_text not in raw and "fake-" not in raw
    assert out.strip().splitlines() == raw.strip().splitlines()
