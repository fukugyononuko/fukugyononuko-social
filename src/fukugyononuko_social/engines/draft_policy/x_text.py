"""X の文字数と URL の判定（DD-06）。twitter-text の設定 v3 に従い、判定は安全側に寄せる。"""

import re
import unicodedata

X_MAX_WEIGHTED_LENGTH = 280
X_URL_LENGTH = 23
# この範囲のコードポイントは 1、それ以外は 2
X_LIGHT_RANGES = ((0, 4351), (8192, 8205), (8208, 8223), (8242, 8247))

# http(s):// のほかに「英数字 . 英字 2 文字以上」も URL とみなす（多めに判定する）。
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


def weighted_length(text: str) -> int:
    normalized = unicodedata.normalize("NFC", text)
    urls = URL_PATTERN.findall(normalized)
    rest = URL_PATTERN.sub("", normalized)
    return X_URL_LENGTH * len(urls) + sum(_weight(c) for c in rest)
