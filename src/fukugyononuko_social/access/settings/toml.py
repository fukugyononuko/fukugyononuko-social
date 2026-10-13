"""CMP-A06 SettingsAccess の実装：settings.toml と禁止語のファイル（DD-12、EIF-03、EIF-04）。"""

import tomllib
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fukugyononuko_social.domain.channel import Channel
from fukugyononuko_social.domain.errors import ExternalFailure, UsageError
from fukugyononuko_social.domain.money import Budget


class TomlSettingsAccess:
    def __init__(self, path: Path) -> None:
        if not path.exists():
            raise UsageError(f"設定ファイルがありません：{path}。リポジトリの settings.example.toml を写して作ってください")
        try:
            self._data = tomllib.loads(path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as e:
            raise UsageError(f"設定ファイルを読めません：{path}：{e}") from e
        self._base = path.parent

    def _path(self, key: str) -> Path:
        try:
            return Path(self._data["paths"][key]).expanduser()
        except KeyError as e:
            raise UsageError(f"設定に paths.{key} がありません") from e

    def price_table(self) -> Mapping[tuple[Channel, str], Decimal]:
        table: dict[tuple[Channel, str], Decimal] = {}
        for channel_name, prices in self._data.get("prices", {}).items():
            try:
                channel = Channel(channel_name)
            except ValueError as e:
                raise UsageError(f"設定の prices に知らないチャネルがあります：{channel_name}") from e
            for operation, value in prices.items():
                try:
                    table[(channel, operation)] = Decimal(str(value))
                except InvalidOperation as e:
                    raise UsageError(f"単価が数ではありません：prices.{channel_name}.{operation}") from e
        return table

    def budget(self) -> Budget:
        try:
            b = self._data["budget"]
            return Budget(monthly_cap_jpy=int(b["monthly_cap_jpy"]), usd_jpy=Decimal(str(b["usd_jpy"])))
        except (KeyError, ValueError, InvalidOperation) as e:
            raise UsageError("設定の budget（monthly_cap_jpy、usd_jpy）が正しくありません") from e

    def denylist(self) -> Sequence[str]:
        path = self._path("denylist")
        try:
            return path.read_text(encoding="utf-8").splitlines()
        except OSError as e:
            raise ExternalFailure(f"禁止語のファイルを読めません：{path.name}") from e

    # 以下は組み立て（composition）だけが使う。契約には含めない
    def report_path(self) -> Path:
        return self._path("report")
