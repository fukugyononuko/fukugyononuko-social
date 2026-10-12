"""CMP-E02 DraftPolicyEngine：下書きを検査する（DD-06、DD-07）。"""

import re
import unicodedata

from fukugyononuko_social.contracts import Channel, ExternalFailure, Finding, SettingsAccess, Severity

# X の数え方（twitter-text の設定 v3）。範囲内のコードポイントは 1、それ以外は 2
X_MAX_WEIGHTED_LENGTH = 280
X_URL_LENGTH = 23
X_LIGHT_RANGES = ((0, 4351), (8192, 8205), (8208, 8223), (8242, 8247))

# 安全側の簡略化（DD-06）：http(s):// のほかに「英数字 . 英字 2 文字以上」も URL とみなす。
# 日本語の直後でも拾えるよう、\b ではなく ASCII の英数字だけを境界として見る。
URL_PATTERN = re.compile(
    r"https?://\S+"
    r"|(?<![0-9A-Za-z-])[0-9A-Za-z][0-9A-Za-z-]*(?:\.[0-9A-Za-z-]+)*\.[A-Za-z]{2,}(?:/[^\s]*)?"
)


def _weight(char: str) -> int:
    code = ord(char)
    return 1 if any(lo <= code <= hi for lo, hi in X_LIGHT_RANGES) else 2


def find_urls(text: str) -> list[str]:
    return URL_PATTERN.findall(unicodedata.normalize("NFC", text))


def x_weighted_length(text: str) -> int:
    normalized = unicodedata.normalize("NFC", text)
    urls = URL_PATTERN.findall(normalized)
    rest = URL_PATTERN.sub("", normalized)
    return X_URL_LENGTH * len(urls) + sum(_weight(c) for c in rest)


def _normalize_for_match(s: str) -> str:
    return unicodedata.normalize("NFKC", s).casefold()


class DefaultDraftPolicyEngine:
    def __init__(self, settings: SettingsAccess) -> None:
        self._settings = settings

    def review(self, channel: Channel, text: str) -> tuple[Finding, ...]:
        findings: list[Finding] = []
        if not text.strip():
            findings.append(Finding(Severity.ERROR, "empty", "本文が空です"))
        findings += self._length(channel, text)
        findings += self._denylist(text)
        if find_urls(text):
            findings.append(
                Finding(
                    Severity.WARNING,
                    "url",
                    "URL（またはドメインに見える語）を含みます。URL 付きの投稿として、高い単価で見積もります",
                )
            )
        return tuple(findings)

    def _length(self, channel: Channel, text: str) -> list[Finding]:
        if channel is Channel.X:
            length = x_weighted_length(text)
            if length > X_MAX_WEIGHTED_LENGTH:
                return [Finding(Severity.ERROR, "length", f"長すぎます（{length} / {X_MAX_WEIGHTED_LENGTH}）")]
            return []
        return [Finding(Severity.ERROR, "channel", f"文字数の規則がないチャネルです：{channel.value}")]

    def _denylist(self, text: str) -> list[Finding]:
        try:
            words = list(self._settings.denylist())
        except ExternalFailure:
            words = []
        entries = [(i, w) for i, w in enumerate(words, start=1) if w.strip() and not w.lstrip().startswith("#")]
        if not entries:
            # 禁止語が読めないまま投稿しない（DD-07）
            return [Finding(Severity.ERROR, "denylist-unavailable", "禁止語のファイルが読めないか空です")]
        target = _normalize_for_match(text)
        # 禁止語そのものは出さず、ファイルの行番号だけを示す
        return [
            Finding(Severity.ERROR, "denylist", f"禁止語（{line} 行目）を含みます")
            for line, word in entries
            if _normalize_for_match(word.strip()) in target
        ]
