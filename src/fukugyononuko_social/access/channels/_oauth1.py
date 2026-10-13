"""OAuth 1.0a（HMAC-SHA1）の署名（RFC 5849、DD-09）。channels の構成要素の中だけで使う。"""

import base64
import hashlib
import hmac
import urllib.parse
from collections.abc import Mapping


def percent_encode(s: str) -> str:
    # RFC 5849 §3.6：英数字と - . _ ~ 以外をすべて符号化する
    return urllib.parse.quote(s, safe="-._~")


def signature(
    method: str, url: str, params: Mapping[str, str], oauth: Mapping[str, str], consumer_secret: str, token_secret: str
) -> str:
    """署名の値（Base64、URL 符号化の前）を返す。params はクエリの引数（JSON の本文は含めない）。"""
    pairs = sorted((percent_encode(k), percent_encode(v)) for k, v in {**params, **oauth}.items())
    normalized = "&".join(f"{k}={v}" for k, v in pairs)
    base = "&".join([method.upper(), percent_encode(url), percent_encode(normalized)])
    key = f"{percent_encode(consumer_secret)}&{percent_encode(token_secret)}"
    return base64.b64encode(hmac.new(key.encode(), base.encode(), hashlib.sha1).digest()).decode()


def header(oauth: Mapping[str, str], sig: str) -> str:
    fields = {**oauth, "oauth_signature": sig}
    return "OAuth " + ", ".join(f'{percent_encode(k)}="{percent_encode(v)}"' for k, v in fields.items())
