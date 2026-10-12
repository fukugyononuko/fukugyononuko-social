"""CMP-A01 ChannelAccess の契約：チャネルの数字を共通の項目名で取得し、投稿する（VOL-01〜VOL-03）。

チャネルごとに、このパッケージの中に実装を置く（初期：x.py）。
"""

from datetime import datetime
from typing import Protocol

from fukugyononuko_social.domain.channel import Channel
from fukugyononuko_social.domain.drafts import PublishedPost
from fukugyononuko_social.domain.metrics import AccountSnapshot, PostMetrics
from fukugyononuko_social.domain.money import Usage


class ChannelAccess(Protocol):
    @property
    def channel(self) -> Channel: ...

    def account_snapshot(self, at: datetime) -> tuple[AccountSnapshot, tuple[Usage, ...]]: ...
    def recent_post_metrics(self, since: datetime, at: datetime) -> tuple[tuple[PostMetrics, ...], tuple[Usage, ...]]: ...
    def post(self, text: str, operation: str) -> PublishedPost: ...
    def usage_upper_bound(self) -> tuple[Usage, ...]:
        """計測 1 回分の、課金される操作の上限（実行前の見積もりに使う）。"""
        ...
