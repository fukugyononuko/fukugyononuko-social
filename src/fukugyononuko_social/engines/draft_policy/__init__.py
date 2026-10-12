"""CMP-E02 DraftPolicyEngine の契約：下書きを検査する（VOL-05、DD-06、DD-07）。"""

from typing import Protocol

from fukugyononuko_social.domain.channel import Channel
from fukugyononuko_social.domain.drafts import Verdict


class DraftPolicyEngine(Protocol):
    def review(self, channel: Channel, text: str) -> Verdict: ...
