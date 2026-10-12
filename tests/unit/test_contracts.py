"""TC-U11：指紋（DD-05）。TC-U12：Secret が値を出さない（DD-13）。"""

import pickle

import pytest

from fukugyononuko_social.contracts import Channel, Secret, fingerprint


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
