"""CMP-M02 PublishingManager の実装（CC-02〜CC-04、DD-20）。"""

import re
from collections.abc import Callable, Mapping, Sequence

from fukugyononuko_social.access.channels import ChannelAccess
from fukugyononuko_social.access.drafts import DraftAccess
from fukugyononuko_social.access.ledger import LedgerAccess
from fukugyononuko_social.domain.channel import Channel, month_of
from fukugyononuko_social.domain.drafts import Draft, DraftStatus, Fail, Pass, Verdict
from fukugyononuko_social.domain.drafts import fingerprint as fingerprint_of
from fukugyononuko_social.domain.errors import BusinessRejection, ExternalFailure, Outcome, UncertainPost
from fukugyononuko_social.domain.money import Usage
from fukugyononuko_social.engines.cost import CostEngine
from fukugyononuko_social.engines.draft_policy import DraftPolicyEngine
from fukugyononuko_social.utilities.clock import Clock
from fukugyononuko_social.utilities.logging import Logging

MIN_FINGERPRINT = 8
MAX_ERROR = 200
_HEX = re.compile(r"[0-9a-f]+")


def post_operation(verdict: Verdict) -> str:
    """投稿の費用の操作の名前。全チャネルで共通（DD-20）。"""
    return "post_create_with_url" if any(w.code == "url" for w in verdict.warnings) else "post_create"


class DefaultPublishingManager:
    def __init__(
        self,
        channels: Mapping[Channel, ChannelAccess],
        drafts: DraftAccess,
        ledger: LedgerAccess,
        policy: DraftPolicyEngine,
        cost: CostEngine,
        clock: Clock,
        log: Logging,
    ) -> None:
        self._channels = channels
        self._drafts = drafts
        self._ledger = ledger
        self._policy = policy
        self._cost = cost
        self._clock = clock
        self._log = log

    def register_draft(self, channel: Channel, text: str) -> Draft:
        def run() -> Draft:
            verdict = self._policy.review(channel, text)
            estimate = self._cost.estimate([Usage(channel, post_operation(verdict), 1)])
            return self._drafts.save_draft(channel, text, verdict, estimate, self._clock.now())

        return self._logged("draft add", run)

    def drafts(self, status: DraftStatus | None = None) -> Sequence[Draft]:
        return self._drafts.drafts(status)

    def draft(self, draft_id: int) -> Draft:
        return self._drafts.find(draft_id)

    def discard(self, draft_id: int) -> Draft:
        return self._logged("discard", lambda: self._drafts.discard(draft_id), draft=draft_id)

    def approve(self, draft_id: int, fingerprint: str) -> Draft:
        def run() -> Draft:
            draft = self._drafts.find(draft_id)
            prefix = fingerprint.strip().lower()
            if len(prefix) < MIN_FINGERPRINT or not _HEX.fullmatch(prefix):
                raise BusinessRejection(f"指紋は {MIN_FINGERPRINT} 文字以上の 16 進で指定してください")
            self._verify_integrity(draft)
            if not draft.fingerprint.startswith(prefix):
                raise BusinessRejection(f"指紋が一致しません。nukosns draft show {draft_id} で文章と指紋を確かめてください")
            return self._drafts.record_approval(draft_id, self._clock.now())

        return self._logged("approve", run, draft=draft_id)

    def publish(self, draft_id: int) -> Draft:
        def run() -> Draft:
            draft = self._drafts.find(draft_id)
            if draft.status not in (DraftStatus.APPROVED, DraftStatus.FAILED):
                raise BusinessRejection(f"下書き {draft_id} は「{draft.status.label}」なので投稿できません")
            self._verify_integrity(draft)
            # 送信直前の再検査（NFR-04）。不合格なら状態は変えない
            match self._policy.review(draft.channel, draft.text):
                case Fail(errors=errors):
                    raise BusinessRejection("再検査で不合格です：" + "／".join(e.message for e in errors))
                case Pass() as verdict:
                    operation = post_operation(verdict)
            estimate = self._cost.estimate([Usage(draft.channel, operation, 1)])
            if not self._cost.afford(estimate, month_of(self._clock.now())):
                raise BusinessRejection(f"今月の上限を超えるため、投稿しません（見積もり {estimate.jpy} 円）")
            channel = self._channels.get(draft.channel)
            if channel is None:
                raise BusinessRejection(f"チャネル {draft.channel.value} には投稿できません（組み立てにありません）")

            self._drafts.mark_sending(draft_id)
            try:
                published = channel.post(draft.text, operation)
            except UncertainPost as e:
                raise UncertainPost(
                    f"{e} 下書き {draft_id} は「送信中」のままです。{draft.channel.value} の画面で投稿されたか確かめてください"
                ) from e
            except ExternalFailure as e:
                self._drafts.record_failed(draft_id, str(e)[:MAX_ERROR])
                raise
            now = self._clock.now()
            result = self._drafts.record_published(draft_id, published.post_id, now)
            if published.usages:
                self._ledger.record_charge(now, self._cost.estimate(published.usages), draft_id=draft_id)
            return result

        return self._logged("publish", run, draft=draft_id)

    def _verify_integrity(self, draft: Draft) -> None:
        if fingerprint_of(draft.channel, draft.text) != draft.fingerprint:
            raise BusinessRejection(f"下書き {draft.id} の文章と指紋が合いません。保存先を確かめてください")

    def _logged(self, command: str, action: Callable[[], Draft], **detail: int | str) -> Draft:
        """結果をログに 1 行残す（文章は書かない。DD-20）。"""
        try:
            draft = action()
        except BusinessRejection:
            self._log.record(command, Outcome.REJECTED, **detail)
            raise
        except ExternalFailure as e:
            self._log.record(command, Outcome.FAILED, error=type(e).__name__, **detail)
            raise
        outcome = Outcome.REJECTED if draft.status is DraftStatus.REJECTED else Outcome.OK
        self._log.record(command, outcome, draft=draft.id, status=draft.status.value, estimate_jpy=draft.estimate.jpy)
        return draft
