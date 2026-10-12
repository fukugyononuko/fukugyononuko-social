"""CMP-U01 Security：macOS キーチェーンから認証情報を読む（DD-13、EIF-06）。"""

import subprocess

from fukugyononuko_social.contracts import Channel, ExternalFailure, Secret

ACCOUNT = "fukugyononuko"


class KeychainSecurity:
    def __init__(self, account: str = ACCOUNT) -> None:
        self._account = account

    def credential(self, channel: Channel, name: str) -> Secret:
        service = f"{channel.value}-{name}"
        try:
            result = subprocess.run(
                ["security", "find-generic-password", "-a", self._account, "-s", service, "-w"],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as e:
            raise ExternalFailure("キーチェーンを読めません（security コマンドがありません）") from e
        if result.returncode != 0 or not result.stdout.strip():
            # コマンドの出力は、値を含むおそれがあるので出さない
            raise ExternalFailure(f"キーチェーンに {service} がありません")
        return Secret(result.stdout.strip())
