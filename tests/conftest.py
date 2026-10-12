"""テスト全体の共通設定。外部の API を呼ばない（NFR-09）ため、ネットワークへの接続を禁止する。"""

import socket

import pytest


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def guard(*args: object, **kwargs: object) -> None:
        raise RuntimeError("テスト中はネットワークに接続しない（NFR-09）")

    monkeypatch.setattr(socket, "socket", guard)
    monkeypatch.setattr(socket, "create_connection", guard)
