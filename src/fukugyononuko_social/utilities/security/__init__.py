"""CMP-U01 Security の契約：認証情報を読み出す（DD-13）。"""

from typing import Protocol

from fukugyononuko_social.domain.channel import Channel
from fukugyononuko_social.domain.secret import Secret


class Security(Protocol):
    def credential(self, channel: Channel, name: str) -> Secret: ...
