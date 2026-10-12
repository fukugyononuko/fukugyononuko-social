"""TC-U11：指紋（DD-05）。TC-U12：Secret が値を出さない（DD-13）。下書きの直和型。"""

import pickle
from datetime import UTC, datetime

import pytest

from fukugyononuko_social.domain.channel import Channel
from fukugyononuko_social.domain.drafts import (
    Approved,
    Discarded,
    DraftStatus,
    Fail,
    Failed,
    Finding,
    Pass,
    Pending,
    Published,
    Rejected,
    Sending,
    Severity,
    fingerprint,
    status_of,
    verdict_of,
)
from fukugyononuko_social.domain.secret import Secret


def test_fingerprint_ignores_nfc_difference() -> None:
    assert fingerprint(Channel.X, "café") == fingerprint(Channel.X, "café")


def test_fingerprint_changes_with_one_character() -> None:
    assert fingerprint(Channel.X, "副業のぬこです") != fingerprint(Channel.X, "副業のぬこです。")
    assert len(fingerprint(Channel.X, "a")) == 64


def test_secret_never_shows_value() -> None:
    s = Secret("very-secret-value")
    for shown in (repr(s), str(s), f"{s}", f"{s!r}", f"{[s]}", f"{ {'k': s} }"):
        assert "very-secret-value" not in shown
    assert s.reveal() == "very-secret-value"
    with pytest.raises(TypeError):
        pickle.dumps(s)


AT = datetime(2026, 10, 12, tzinfo=UTC)


def test_every_state_has_a_status() -> None:
    states = [
        Rejected(errors=(Finding(Severity.ERROR, "x", "x"),)),
        Pending(),
        Approved(AT),
        Sending(AT),
        Published(AT, "1", AT),
        Failed(AT, "e"),
        Discarded(),
    ]
    assert [status_of(s) for s in states] == list(DraftStatus)


def test_fail_needs_a_reason() -> None:
    with pytest.raises(ValueError):
        Fail(errors=())


def test_verdict_of_splits_errors_and_warnings() -> None:
    e = Finding(Severity.ERROR, "e", "e")
    w = Finding(Severity.WARNING, "w", "w")
    assert verdict_of((w,)) == Pass(warnings=(w,))
    assert verdict_of((e, w)) == Fail(errors=(e,), warnings=(w,))
