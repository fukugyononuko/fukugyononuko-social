"""組み立て（DD-15）。具体的な実装を知っているのは、ここだけ。

動かす場所を変えるとき（Google Cloud など）は、ここで実装を差し替える（VOL-08〜VOL-12）。
"""

import os
import sys
from collections.abc import Sequence
from pathlib import Path

from fukugyononuko_social.access._sqlite import connect
from fukugyononuko_social.access.channels import ChannelAccess
from fukugyononuko_social.access.channels.x import XChannelAccess
from fukugyononuko_social.access.drafts.sqlite import SqliteDraftAccess
from fukugyononuko_social.access.ledger.sqlite import SqliteLedgerAccess
from fukugyononuko_social.access.metrics.sqlite import SqliteMetricsAccess
from fukugyononuko_social.access.report.markdown import MarkdownReportAccess
from fukugyononuko_social.access.settings.toml import TomlSettingsAccess
from fukugyononuko_social.clients.cli import App
from fukugyononuko_social.clients.cli.main import run
from fukugyononuko_social.engines.aggregation.default import DefaultAggregationEngine
from fukugyononuko_social.engines.cost.default import DefaultCostEngine
from fukugyononuko_social.engines.draft_policy.default import DefaultDraftPolicyEngine
from fukugyononuko_social.managers.measurement.default import DefaultMeasurementManager
from fukugyononuko_social.managers.publishing.default import DefaultPublishingManager
from fukugyononuko_social.utilities.clock.system import SystemClock
from fukugyononuko_social.utilities.logging.jsonl import JsonLinesLog
from fukugyononuko_social.utilities.security.keychain import KeychainSecurity

DEFAULT_HOME = "~/fukugyononuko/data/fukugyononuko-social"


def home() -> Path:
    """保存先のフォルダ。環境変数 NUKOSNS_HOME で変えられる（総合テスト用）。"""
    return Path(os.environ.get("NUKOSNS_HOME", DEFAULT_HOME)).expanduser()


def build(base: Path, channels: Sequence[ChannelAccess] | None = None) -> App:
    clock = SystemClock()
    log = JsonLinesLog(base / "logs" / "nukosns.log", clock)
    settings = TomlSettingsAccess(base / "settings.toml")
    conn = connect(base / "nukosns.sqlite")
    metrics = SqliteMetricsAccess(conn)
    ledger = SqliteLedgerAccess(conn)
    cost = DefaultCostEngine(settings, ledger)
    if channels is None:
        channels = (XChannelAccess(KeychainSecurity()),)
    measurement = DefaultMeasurementManager(
        channels,
        metrics,
        ledger,
        MarkdownReportAccess(settings.report_path()),
        DefaultAggregationEngine(metrics, ledger),
        cost,
        clock,
        log,
    )
    publishing = DefaultPublishingManager(
        {c.channel: c for c in channels},
        SqliteDraftAccess(conn),
        ledger,
        DefaultDraftPolicyEngine(settings),
        cost,
        clock,
        log,
    )
    return App(measurement=measurement, publishing=publishing, log=log)


def main(argv: Sequence[str] | None = None) -> int:
    return run(argv, lambda: build(home()))


if __name__ == "__main__":
    sys.exit(main())
