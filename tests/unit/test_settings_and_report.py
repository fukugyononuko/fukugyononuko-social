"""CMP-A06 設定（DD-12）と CMP-A05 書き出し（DD-11）。TC-N03 の一部（設定の場所はリポジトリの外）。"""

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from fukugyononuko_social.access.report.markdown import MarkdownReportAccess, render
from fukugyononuko_social.access.settings.toml import TomlSettingsAccess
from fukugyononuko_social.domain.channel import Channel
from fukugyononuko_social.domain.errors import ExternalFailure, Outcome, UsageError
from fukugyononuko_social.domain.metrics import Finished, MonthlyRow, PostMetrics, Report

ROOT = Path(__file__).resolve().parents[2]
AT = datetime(2026, 10, 13, 0, tzinfo=UTC)


def write_settings(tmp_path: Path, denylist: Path) -> Path:
    text = (ROOT / "settings.example.toml").read_text(encoding="utf-8")
    text = text.replace("~/fukugyononuko/projects/fukugyononuko.github.io/.privacy-denylist", str(denylist))
    path = tmp_path / "settings.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_example_settings_are_loadable(tmp_path: Path) -> None:
    denylist = tmp_path / "denylist"
    denylist.write_text("# 注釈\n語\n", encoding="utf-8")
    settings = TomlSettingsAccess(write_settings(tmp_path, denylist))
    assert settings.price_table()[(Channel.X, "post_create_with_url")] == Decimal("0.200")
    budget = settings.budget()
    assert (budget.monthly_cap_jpy, budget.usd_jpy) == (500, Decimal(170))
    assert list(settings.denylist()) == ["# 注釈", "語"]
    assert settings.report_path() == Path("~/fukugyononuko/vault/50-Metrics/SNS.md").expanduser()


def test_missing_settings_is_usage_error(tmp_path: Path) -> None:
    with pytest.raises(UsageError, match="settings.example.toml"):
        TomlSettingsAccess(tmp_path / "none.toml")


def test_unreadable_denylist_is_external_failure_without_path_detail(tmp_path: Path) -> None:
    settings = TomlSettingsAccess(write_settings(tmp_path, tmp_path / "missing-denylist"))
    with pytest.raises(ExternalFailure):
        settings.denylist()


def test_n03_default_locations_are_outside_the_repository() -> None:
    import tomllib

    paths = tomllib.loads((ROOT / "settings.example.toml").read_text(encoding="utf-8"))["paths"]
    for value in paths.values():
        assert not Path(value).expanduser().resolve().is_relative_to(ROOT)


REPORT = Report(
    generated_at=AT,
    monthly=(MonthlyRow("2026-10", Channel.X, 26, 26, 5, 187, 5, 4, 0, 12),),
    recent_posts=(PostMetrics(Channel.X, "1", AT, AT, "表に | を含む本文", impressions=52, likes=2, profile_clicks=None),),
    last_run=Finished(1, AT, AT, Outcome.OK),
)


def test_render_contains_rows_and_escapes_pipes() -> None:
    text = render(REPORT)
    assert "| 2026-10 | x | 26 | 26 | 5 | 187 | 5 | 4 | 0 | 12 |" in text
    assert "表に ｜ を含む本文" in text
    assert "| 2026-10-13 | x | 52 | 2 | ― |" in text
    assert "2026-10-13 09:00：ok" in text  # 日本時間で表示する


def test_publish_replaces_whole_file_without_leftovers(tmp_path: Path) -> None:
    path = tmp_path / "vault" / "50-Metrics" / "SNS.md"
    report = MarkdownReportAccess(path)
    report.publish_report(REPORT)
    path.write_text("手で書き足した行", encoding="utf-8")
    report.publish_report(REPORT)
    assert path.read_text(encoding="utf-8") == render(REPORT)
    assert [p.name for p in path.parent.iterdir()] == ["SNS.md"]
