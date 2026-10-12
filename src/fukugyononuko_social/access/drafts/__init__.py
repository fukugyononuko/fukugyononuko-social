"""CMP-A03 DraftAccess の契約：下書きと、その状態の遷移（DD-03 drafts、DD-04）。

保存先の行と、直和型の DraftState との変換は、この構成要素の中で 1 回だけ行う。
許されない遷移は BusinessRejection で拒否する。
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from fukugyononuko_social.domain.channel import Channel
from fukugyononuko_social.domain.drafts import Draft, DraftStatus, Verdict
from fukugyononuko_social.domain.money import Cost


class DraftAccess(Protocol):
    def save_draft(self, channel: Channel, text: str, verdict: Verdict, estimate: Cost, at: datetime) -> Draft:
        """Fail なら「不合格」、Pass なら「下書き」として保存する。"""
        ...

    def find(self, draft_id: int) -> Draft: ...
    def drafts(self, status: DraftStatus | None = None) -> Sequence[Draft]: ...
    def record_approval(self, draft_id: int, at: datetime) -> Draft: ...
    def mark_sending(self, draft_id: int) -> Draft: ...
    def record_published(self, draft_id: int, post_id: str, at: datetime) -> Draft: ...
    def record_failed(self, draft_id: int, error: str) -> Draft: ...
    def discard(self, draft_id: int) -> Draft: ...
