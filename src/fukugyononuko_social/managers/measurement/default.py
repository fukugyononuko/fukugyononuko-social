"""CMP-M01 MeasurementManager の実装（CC-01、CC-05、DD-19）。"""

from collections.abc import Callable, Sequence
from datetime import datetime, timedelta

from fukugyononuko_social.access.channels import ChannelAccess
from fukugyononuko_social.access.ledger import LedgerAccess
from fukugyononuko_social.access.metrics import MetricsAccess
from fukugyononuko_social.access.report import ReportAccess
from fukugyononuko_social.access.transaction import TransactionAccess
from fukugyononuko_social.domain.channel import month_of
from fukugyononuko_social.domain.errors import BusinessRejection, ExternalFailure, Outcome
from fukugyononuko_social.domain.metrics import AccountSnapshot, MeasurementSummary, PartialFetch, PostMetrics
from fukugyononuko_social.domain.money import BudgetStatus, Usage
from fukugyononuko_social.engines.aggregation import AggregationEngine
from fukugyononuko_social.engines.cost import CostEngine
from fukugyononuko_social.utilities.clock import Clock
from fukugyononuko_social.utilities.logging import Logging

# 本人だけの数字は投稿から 30 日以内しか取れないため、29 日に絞る（EIF-01）
LOOKBACK = timedelta(days=29)
COMMAND = "measure"


class DefaultMeasurementManager:
    def __init__(
        self,
        channels: Sequence[ChannelAccess],
        metrics: MetricsAccess,
        ledger: LedgerAccess,
        report: ReportAccess,
        transaction: TransactionAccess,
        aggregation: AggregationEngine,
        cost: CostEngine,
        clock: Clock,
        log: Logging,
    ) -> None:
        self._channels = channels
        self._metrics = metrics
        self._ledger = ledger
        self._report = report
        self._transaction = transaction
        self._aggregation = aggregation
        self._cost = cost
        self._clock = clock
        self._log = log

    def measure(self) -> MeasurementSummary:
        now = self._clock.now()
        run_id = self._metrics.start_run(now)
        try:
            upper = self._cost.estimate([u for ch in self._channels for u in ch.usage_upper_bound()])
            if not self._cost.afford(upper, month_of(now)):
                self._finish(run_id, Outcome.REJECTED, estimate_jpy=upper.jpy)
                raise BusinessRejection(f"今月の上限を超えるため、計測しません（見積もり {upper.jpy} 円）")

            accounts = posts = cost_jpy = 0
            failed: list[str] = []
            for channel in self._channels:
                got_accounts, got_posts, usages, error = self._fetch(channel, now, self._may_spend(month_of(now)))
                charge = self._cost.estimate(usages) if usages else None
                # 数字の保存と費用の記録は、まとめて確定する（DD-21）
                with self._transaction.atomically():
                    self._metrics.record(run_id, got_accounts, got_posts)
                    if charge is not None:
                        self._ledger.record_charge(self._clock.now(), charge, run_id=run_id)
                cost_jpy += charge.jpy if charge is not None else 0
                accounts += len(got_accounts)
                posts += len(got_posts)
                if error is not None:
                    failed.append(f"{channel.channel.value}：{error}")

            summary = MeasurementSummary(run_id, accounts, posts, cost_jpy)
            if failed:
                # 一部のチャネルだけ新しい表にしないため、集計は書き換えない（DD-19）
                self._finish(run_id, Outcome.FAILED, accounts=accounts, posts=posts, cost_jpy=cost_jpy, failed=len(failed))
                raise ExternalFailure("取得に失敗したチャネルがあります。集計は前回のままです：" + "／".join(failed))

            self._metrics.finish_run(run_id, self._clock.now(), Outcome.OK)
            try:
                self._report.publish_report(self._aggregation.summarize(self._clock.now()))
            except OSError as e:
                self._log.record(COMMAND, Outcome.FAILED, run=run_id, report=type(e).__name__)
                raise ExternalFailure(f"集計を書き出せません（数字は保存済みです）：{type(e).__name__}") from e
            self._log.record(COMMAND, Outcome.OK, run=run_id, accounts=accounts, posts=posts, cost_jpy=cost_jpy)
            return summary
        except BusinessRejection, ExternalFailure:
            raise
        except Exception as e:
            # 想定外の失敗でも、計測を「実行中」のまま残さない
            self._finish(run_id, Outcome.FAILED, error=type(e).__name__)
            raise

    def cost_status(self, month: str | None = None) -> BudgetStatus:
        return self._cost.status(month or month_of(self._clock.now()))

    def _may_spend(self, month: str) -> Callable[[Sequence[Usage]], bool]:
        """ページごとの上限の判定（DD-09）。記録済みの費用（先に取ったチャネルの分も含む）に足して判定する。"""
        return lambda usages: self._cost.afford(self._cost.estimate(usages), month)

    def _fetch(
        self, channel: ChannelAccess, now: datetime, may_spend: Callable[[Sequence[Usage]], bool]
    ) -> tuple[list[AccountSnapshot], list[PostMetrics], list[Usage], str | None]:
        """1 つのチャネルから取得する。失敗しても、それまでに取れた分と課金された操作を返す（DD-09、DD-19）。"""
        accounts: list[AccountSnapshot] = []
        usages: list[Usage] = []
        try:
            snapshot, used = channel.account_snapshot(now)
            accounts.append(snapshot)
            usages += used
            posts, used = channel.recent_post_metrics(now - LOOKBACK, now, lambda more: may_spend([*usages, *more]))
            usages += used
            return accounts, list(posts), usages, None
        except PartialFetch as e:
            return accounts, list(e.posts), usages + list(e.usages), str(e)
        except ExternalFailure as e:
            return accounts, [], usages, str(e)

    def _finish(self, run_id: int, outcome: Outcome, **detail: int | str) -> None:
        self._metrics.finish_run(run_id, self._clock.now(), outcome)
        self._log.record(COMMAND, outcome, run=run_id, **detail)
