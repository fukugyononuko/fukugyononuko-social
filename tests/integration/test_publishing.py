"""TC-I04〜I07、I10：CMP-M02 PublishingManager（CC-02〜CC-04、DD-20）。

下書きの保存先は、状態遷移の拒否まで確かめるため、メモリ上の SQLite を使う。
"""

from datetime import UTC, datetime

import pytest

from fukugyononuko_social.access._sqlite import connect
from fukugyononuko_social.access.drafts.sqlite import SqliteDraftAccess
from fukugyononuko_social.domain.channel import Channel
from fukugyononuko_social.domain.drafts import DraftStatus, Failed, Published
from fukugyononuko_social.domain.errors import BusinessRejection, ExternalFailure, Outcome, UncertainPost
from fukugyononuko_social.engines.cost.default import DefaultCostEngine
from fukugyononuko_social.engines.draft_policy.default import DefaultDraftPolicyEngine
from fukugyononuko_social.managers.publishing.default import DefaultPublishingManager
from tests.fakes import FakeChannel, FakeLedger, FakeLog, FakeSettings, FixedClock

NOW = datetime(2026, 10, 19, 0, tzinfo=UTC)


class World:
    def __init__(self, channel: FakeChannel | None = None, cap_jpy: int = 500) -> None:
        self.channel = channel or FakeChannel()
        self.ledger = FakeLedger()
        self.log = FakeLog()
        self.settings = FakeSettings(cap_jpy=cap_jpy)
        self.drafts = SqliteDraftAccess(connect(":memory:"))
        self.manager = DefaultPublishingManager(
            {Channel.X: self.channel},
            self.drafts,
            self.ledger,
            DefaultDraftPolicyEngine(self.settings),
            DefaultCostEngine(self.settings, self.ledger),
            FixedClock(NOW),
            self.log,
        )

    def approved(self, text: str = "こんにちは") -> int:
        d = self.manager.register_draft(Channel.X, text)
        self.manager.approve(d.id, d.fingerprint[:8])
        return d.id


def test_i04_draft_with_denied_word_is_saved_as_rejected() -> None:
    w = World()
    d = w.manager.register_draft(Channel.X, "これは禁止語いちを含む")
    assert d.status is DraftStatus.REJECTED
    assert w.drafts.find(d.id).status is DraftStatus.REJECTED
    assert w.log.lines[-1][:2] == ("draft add", Outcome.REJECTED)
    assert "禁止語いち" not in str(w.log.lines)  # 文章もログに出さない


def test_i04_estimate_uses_url_price_when_url_is_present() -> None:
    w = World()
    assert w.manager.register_draft(Channel.X, "こんにちは").estimate.jpy == 3  # $0.015 → 2.55 → 3 円
    assert w.manager.register_draft(Channel.X, "詳しくは example.com で").estimate.jpy == 34  # $0.200 → 34 円


def test_i05_approval_requires_matching_fingerprint() -> None:
    w = World()
    d = w.manager.register_draft(Channel.X, "こんにちは")
    other = "0" * 8 if not d.fingerprint.startswith("0" * 8) else "1" * 8
    for given in (other, d.fingerprint[:7], "zzzzzzzz"):
        with pytest.raises(BusinessRejection):
            w.manager.approve(d.id, given)
    assert w.drafts.find(d.id).status is DraftStatus.PENDING
    assert w.manager.approve(d.id, d.fingerprint[:8].upper()).status is DraftStatus.APPROVED


def test_i06_unapproved_draft_is_not_posted() -> None:
    w = World()
    d = w.manager.register_draft(Channel.X, "こんにちは")
    with pytest.raises(BusinessRejection, match="下書き"):
        w.manager.publish(d.id)
    assert w.channel.calls == []


def test_i06_recheck_before_sending() -> None:
    w = World()
    draft_id = w.approved("あとで禁止になる言葉")
    assert w.settings.words is not None
    w.settings.words.append("あとで禁止")
    with pytest.raises(BusinessRejection, match="再検査"):  # 承認後に禁止語が増えても、送信直前の検査で止まる
        w.manager.publish(draft_id)
    w.settings.words = None  # 禁止語が読めないときも止まる
    with pytest.raises(BusinessRejection):
        w.manager.publish(draft_id)
    assert w.channel.calls == []
    assert w.drafts.find(draft_id).status is DraftStatus.APPROVED


def test_publish_success_records_post_and_charge() -> None:
    w = World()
    draft_id = w.approved()
    d = w.manager.publish(draft_id)
    assert isinstance(d.state, Published) and d.state.post_id == "p1"
    assert w.channel.sent == [("こんにちは", "post_create")]
    assert [c.jpy for _, c in w.ledger.charges] == [3]
    assert w.ledger.links == [(None, draft_id)]
    with pytest.raises(BusinessRejection):  # 投稿済みは二度と送らない（NFR-06）
        w.manager.publish(draft_id)
    assert len(w.channel.sent) == 1


def test_publish_rejected_over_budget() -> None:
    w = World(cap_jpy=2)
    draft_id = w.approved()
    with pytest.raises(BusinessRejection, match="上限"):
        w.manager.publish(draft_id)
    assert w.drafts.find(draft_id).status is DraftStatus.APPROVED


def test_i07_api_failure_marks_failed_and_can_be_resent() -> None:
    w = World(FakeChannel(fail={"post"}))
    draft_id = w.approved()
    with pytest.raises(ExternalFailure):
        w.manager.publish(draft_id)
    d = w.drafts.find(draft_id)
    assert isinstance(d.state, Failed) and "403" in d.state.error
    assert w.ledger.charges == []
    w.channel.fail.clear()
    assert w.manager.publish(draft_id).status is DraftStatus.PUBLISHED


def test_i07_sending_is_not_resent() -> None:
    w = World()
    draft_id = w.approved()
    w.drafts.mark_sending(draft_id)  # 前回の投稿の途中で落ちた
    with pytest.raises(BusinessRejection, match="送信中"):
        w.manager.publish(draft_id)
    assert w.channel.calls == []


def test_i10_uncertain_post_stays_sending_without_charge() -> None:
    w = World(FakeChannel(fail={"uncertain"}))
    draft_id = w.approved()
    with pytest.raises(UncertainPost, match="送信中"):
        w.manager.publish(draft_id)
    assert w.drafts.find(draft_id).status is DraftStatus.SENDING
    assert w.ledger.charges == []
    assert w.log.lines[-1][:2] == ("publish", Outcome.FAILED)


def test_discard_and_listing() -> None:
    w = World()
    a = w.manager.register_draft(Channel.X, "ひとつめ")
    w.manager.register_draft(Channel.X, "ふたつめ")
    w.manager.discard(a.id)
    assert [d.id for d in w.manager.drafts(DraftStatus.PENDING)] == [a.id + 1]
    assert w.manager.draft(a.id).status is DraftStatus.DISCARDED
