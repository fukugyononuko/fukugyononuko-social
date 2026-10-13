"""例外と、実行の結果（DD-18）。"""

from enum import StrEnum


class Outcome(StrEnum):
    OK = "ok"
    REJECTED = "rejected"
    FAILED = "failed"


class BusinessRejection(Exception):
    """検査の不合格、上限の超過、承認なし、指紋の不一致、許されない遷移。終了コード 1。"""


class UsageError(Exception):
    """引数の誤り、設定ファイルがない。終了コード 2。"""


class ExternalFailure(Exception):
    """API・キーチェーン・保存先の失敗。終了コード 3。"""


class UncertainPost(ExternalFailure):
    """投稿されたかどうかわからない失敗（5xx・タイムアウト・接続の失敗。DD-09）。下書きは「送信中」のまま残す。"""
