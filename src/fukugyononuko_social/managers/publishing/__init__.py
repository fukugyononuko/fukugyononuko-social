"""CMP-M02 PublishingManager の契約：UC-02（承認つきの投稿）の流れ（CC-02〜CC-04、DD-20）。"""

from collections.abc import Sequence
from typing import Protocol

from fukugyononuko_social.domain.channel import Channel
from fukugyononuko_social.domain.drafts import Draft, DraftStatus


class PublishingManager(Protocol):
    def register_draft(self, channel: Channel, text: str) -> Draft:
        """検査と見積もりをして保存する。不合格でも保存し、状態が「不合格」の下書きを返す。"""
        ...

    def drafts(self, status: DraftStatus | None = None) -> Sequence[Draft]: ...
    def draft(self, draft_id: int) -> Draft: ...
    def discard(self, draft_id: int) -> Draft: ...
    def approve(self, draft_id: int, fingerprint: str) -> Draft: ...
    def publish(self, draft_id: int) -> Draft:
        """承認済み（または失敗）の下書きを投稿する。投稿されたかわからないときは UncertainPost。"""
        ...
