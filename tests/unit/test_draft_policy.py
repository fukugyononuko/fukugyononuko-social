"""TC-U01〜U03：CMP-E02 DraftPolicyEngine（DD-06、DD-07）。"""

import pytest

from fukugyononuko_social.contracts import Channel, Severity
from fukugyononuko_social.engines.draft_policy import DefaultDraftPolicyEngine, find_urls, x_weighted_length
from tests.fakes import FakeSettings


def codes(findings: tuple) -> set[str]:
    return {f.code for f in findings}


def errors(findings: tuple) -> set[str]:
    return {f.code for f in findings if f.severity is Severity.ERROR}


# TC-U01 文字数
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("abc", 3),
        ("副業", 4),
        ("🐶", 2),  # 範囲外のコードポイントは 2
        ("a https://example.com/very/long/path b", 2 + 23 + 2),
    ],
)
def test_weighted_length(text: str, expected: int) -> None:
    assert x_weighted_length(text) == expected


def test_nfc_normalization() -> None:
    assert x_weighted_length("café") == x_weighted_length("café") == 4


def test_limit_boundary() -> None:
    engine = DefaultDraftPolicyEngine(FakeSettings())
    assert "length" not in errors(engine.review(Channel.X, "a" * 280))
    assert "length" in errors(engine.review(Channel.X, "a" * 281))
    assert "length" in errors(engine.review(Channel.X, "あ" * 141))
    assert "length" not in errors(engine.review(Channel.X, "あ" * 140))


# TC-U02 URL の判定
@pytest.mark.parametrize("text", ["見て https://example.com", "見てexample.com", "note.com/abc を読んで"])
def test_url_detected(text: str) -> None:
    assert find_urls(text)
    findings = DefaultDraftPolicyEngine(FakeSettings()).review(Channel.X, text)
    assert "url" in codes(findings)
    assert "url" not in errors(findings)  # URL は注意（費用の差）であって不合格ではない


def test_no_url_in_plain_text() -> None:
    assert find_urls("Python / Rust / Google Cloud。0→1 で収益化") == []


# TC-U03 禁止語
def test_denylist_matches_case_and_width() -> None:
    engine = DefaultDraftPolicyEngine(FakeSettings())
    for text in ["これは禁止語いちです", "ＦＯＲＢＩＤＤＥＮ word", "forbidden"]:
        findings = engine.review(Channel.X, text)
        assert "denylist" in errors(findings)


def test_denylist_message_hides_word() -> None:
    findings = DefaultDraftPolicyEngine(FakeSettings()).review(Channel.X, "これは禁止語いちです")
    messages = " ".join(f.message for f in findings)
    assert "禁止語いち" not in messages
    assert "2 行目" in messages  # 1 行目は注釈


def test_comment_lines_are_not_words() -> None:
    assert "denylist" not in errors(DefaultDraftPolicyEngine(FakeSettings()).review(Channel.X, "# 注釈 という文字"))


@pytest.mark.parametrize("words", [None, [], ["# 注釈だけ", "  "]])
def test_unreadable_or_empty_denylist_rejects(words: list[str] | None) -> None:
    findings = DefaultDraftPolicyEngine(FakeSettings(words=words)).review(Channel.X, "ふつうの文章")
    assert "denylist-unavailable" in errors(findings)


def test_clean_text_passes() -> None:
    assert errors(DefaultDraftPolicyEngine(FakeSettings()).review(Channel.X, "副業のぬこです🐶")) == set()


def test_empty_text_rejected() -> None:
    assert "empty" in errors(DefaultDraftPolicyEngine(FakeSettings()).review(Channel.X, "  \n"))
