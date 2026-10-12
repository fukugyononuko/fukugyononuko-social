"""CMP-E02 DraftPolicyEngine の実装（DD-06、DD-07）。"""

import unicodedata

from fukugyononuko_social.access.settings import SettingsAccess
from fukugyononuko_social.domain.channel import Channel
from fukugyononuko_social.domain.drafts import Finding, Severity, Verdict, verdict_of
from fukugyononuko_social.domain.errors import ExternalFailure
from fukugyononuko_social.engines.draft_policy import x_text


def _normalize_for_match(s: str) -> str:
    return unicodedata.normalize("NFKC", s).casefold()


class DefaultDraftPolicyEngine:
    def __init__(self, settings: SettingsAccess) -> None:
        self._settings = settings

    def review(self, channel: Channel, text: str) -> Verdict:
        findings: list[Finding] = []
        if not text.strip():
            findings.append(Finding(Severity.ERROR, "empty", "本文が空です"))
        findings += self._length(channel, text)
        findings += self._denylist(text)
        if x_text.find_urls(text):
            findings.append(
                Finding(
                    Severity.WARNING,
                    "url",
                    "URL（またはドメインに見える語）を含みます。URL 付きの投稿として、高い単価で見積もります",
                )
            )
        return verdict_of(tuple(findings))

    def _length(self, channel: Channel, text: str) -> list[Finding]:
        match channel:
            case Channel.X:
                length = x_text.weighted_length(text)
                if length > x_text.X_MAX_WEIGHTED_LENGTH:
                    return [Finding(Severity.ERROR, "length", f"長すぎます（{length} / {x_text.X_MAX_WEIGHTED_LENGTH}）")]
                return []

    def _denylist(self, text: str) -> list[Finding]:
        try:
            lines = list(self._settings.denylist())
        except ExternalFailure:
            lines = []
        entries = [(i, w.strip()) for i, w in enumerate(lines, start=1) if w.strip() and not w.lstrip().startswith("#")]
        if not entries:
            # 禁止語が読めないまま投稿しない（DD-07）
            return [Finding(Severity.ERROR, "denylist-unavailable", "禁止語のファイルが読めないか空です")]
        target = _normalize_for_match(text)
        # 禁止語そのものは出さず、ファイルの行番号だけを示す
        return [
            Finding(Severity.ERROR, "denylist", f"禁止語（{line} 行目）を含みます")
            for line, word in entries
            if _normalize_for_match(word) in target
        ]
