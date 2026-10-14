"""CMP-U01・U02 の単体テスト。TC-N02 の一部（ログに認証情報・全文が出ない）。"""

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from fukugyononuko_social.domain.channel import Channel
from fukugyononuko_social.domain.errors import ExternalFailure, Outcome
from fukugyononuko_social.domain.secret import Secret
from fukugyononuko_social.utilities.logging.jsonl import JsonLinesLog
from fukugyononuko_social.utilities.security.keychain import KeychainSecurity
from tests.fakes import FixedClock

CLOCK = FixedClock(datetime(2026, 10, 12, 0, tzinfo=UTC))


def test_log_writes_json_lines(tmp_path: Path) -> None:
    log = JsonLinesLog(tmp_path / "logs" / "nukosns.log", CLOCK)
    log.record("measure", Outcome.OK, posts=5, cost_jpy=3)
    log.record("publish", Outcome.REJECTED, draft=2)
    lines = [json.loads(line) for line in (tmp_path / "logs" / "nukosns.log").read_text().splitlines()]
    assert lines[0] == {
        "at": "2026-10-12T00:00:00+00:00",
        "command": "measure",
        "outcome": "ok",
        "detail": {"cost_jpy": 3, "posts": 5},
    }
    assert lines[1]["outcome"] == "rejected"


def test_log_refuses_secret_and_long_text(tmp_path: Path) -> None:
    log = JsonLinesLog(tmp_path / "nukosns.log", CLOCK)
    with pytest.raises(TypeError):
        log.record("x", Outcome.OK, token=Secret("v"))  # ty: ignore[invalid-argument-type]
    with pytest.raises(ValueError):
        log.record("x", Outcome.OK, text="あ" * 201)
    assert not (tmp_path / "nukosns.log").exists()


def test_keychain_reads_value(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[list[str]] = []

    def fake_run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        seen.append(args)
        return subprocess.CompletedProcess(args, 0, stdout="the-value\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    secret = KeychainSecurity().credential(Channel.X, "api-key")
    assert secret.reveal() == "the-value"
    assert seen[0][-3:] == ["-s", "x-api-key", "-w"]


def test_keychain_failure_hides_output(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 44, stdout="leaked-value", stderr="leaked-error")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(ExternalFailure) as e:
        KeychainSecurity().credential(Channel.X, "api-key")
    assert "leaked" not in str(e.value)
    assert "x-api-key" in str(e.value)


def test_log_recent_returns_last_lines(tmp_path: Path) -> None:
    log = JsonLinesLog(tmp_path / "nukosns.log", CLOCK)
    assert log.recent(5) == []
    for i in range(3):
        log.record("measure", Outcome.OK, run=i)
    lines = log.recent(2)
    assert [json.loads(line)["detail"]["run"] for line in lines] == [1, 2]
