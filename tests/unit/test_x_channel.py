"""TC-U07〜U09：CMP-A01 の X の実装（DD-09）。X の応答は、テスト用に作った JSON で代わりにする。"""

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime

import pytest

from fukugyononuko_social.access.channels import _oauth1
from fukugyononuko_social.access.channels.x import Response, XChannelAccess
from fukugyononuko_social.domain.channel import Channel
from fukugyononuko_social.domain.errors import ExternalFailure
from fukugyononuko_social.domain.money import Usage
from fukugyononuko_social.domain.secret import Secret

AT = datetime(2026, 10, 13, 0, tzinfo=UTC)
SINCE = datetime(2026, 9, 14, 0, tzinfo=UTC)

ME = {"data": {"id": "100", "public_metrics": {"followers_count": 26, "following_count": 26, "tweet_count": 5}}}


def tweet(post_id: str, impressions: int, with_private: bool = True) -> dict:
    t = {
        "id": post_id,
        "created_at": "2026-10-10T11:15:54.000Z",
        "text": f"テスト用の投稿 {post_id}\n二行目",
        "public_metrics": {
            "impression_count": impressions,
            "like_count": 2,
            "reply_count": 1,
            "retweet_count": 0,
            "quote_count": 0,
            "bookmark_count": 3,
        },
    }
    if with_private:
        t["non_public_metrics"] = {"impression_count": impressions, "user_profile_clicks": 4, "url_link_clicks": 0}
    return t


class FakeSecurity:
    def credential(self, channel: Channel, name: str) -> Secret:
        return Secret(f"fake-{name}")


class FakeTransport:
    """順番に応答を返し、受け取ったリクエストを記録する。"""

    def __init__(self, *responses: Response | Exception) -> None:
        self.responses = list(responses)
        self.requests: list[urllib.request.Request] = []

    def __call__(self, request: urllib.request.Request) -> Response:
        self.requests.append(request)
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def ok(body: dict, status: int = 200) -> Response:
    return Response(status, {}, json.dumps(body).encode())


def make(transport: FakeTransport, sleeps: list[float] | None = None, jitter: float = 0.5) -> XChannelAccess:
    record = sleeps if sleeps is not None else []
    return XChannelAccess(FakeSecurity(), transport, sleep=record.append, jitter=lambda: jitter, epoch=lambda: 1_000_000.0)


# TC-U07：RFC 5849 §1.2 の例と同じ署名になる
def test_u07_signature_matches_rfc5849_example() -> None:
    oauth = {
        "oauth_consumer_key": "dpf43f3p2l4k3l03",
        "oauth_token": "nnch734d00sl2jdk",
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": "137131202",
        "oauth_nonce": "chapoH",
    }
    sig = _oauth1.signature(
        "GET",
        "http://photos.example.net/photos",
        {"file": "vacation.jpg", "size": "original"},
        oauth,
        "kd94hf93k423kf44",
        "pfkkdhi9sl3r4s00",
    )
    assert sig == "MdpQcU8iPSUjWoN/UDMsK2sui9I="
    assert _oauth1.percent_encode(sig) == "MdpQcU8iPSUjWoN%2FUDMsK2sui9I%3D"


def test_u07_requests_are_signed_and_secret_free_in_url() -> None:
    transport = FakeTransport(ok(ME))
    make(transport).account_snapshot(AT)
    request = transport.requests[0]
    assert request.get_header("Authorization", "").startswith("OAuth ")
    assert "fake-api-key-secret" not in request.full_url
    assert "fake-api-key-secret" not in request.get_header("Authorization", "")


# TC-U08：共通の項目名に揃う。取れない項目は None
def test_u08_account_and_posts_are_mapped() -> None:
    transport = FakeTransport(ok(ME), ok({"data": [tweet("1", 52), tweet("2", 20, with_private=False)], "meta": {}}))
    x = make(transport)
    snapshot, usages = x.account_snapshot(AT)
    assert (snapshot.followers, snapshot.following, snapshot.posts) == (26, 26, 5)
    assert usages == (Usage(Channel.X, "user_read", 1),)

    posts, usages = x.recent_post_metrics(SINCE, AT)
    first, second = posts
    assert (first.impressions, first.likes, first.replies, first.bookmarks, first.profile_clicks) == (52, 2, 1, 3, 4)
    assert first.text_head == "テスト用の投稿 1 二行目"
    assert first.created_at == datetime(2026, 10, 10, 11, 15, 54, tzinfo=UTC)
    assert (second.profile_clicks, second.link_clicks) == (None, None)
    assert usages == (Usage(Channel.X, "post_read", 2),)
    query = urllib.parse.parse_qs(urllib.parse.urlparse(transport.requests[1].full_url).query)
    assert query["start_time"] == ["2026-09-14T00:00:00Z"]
    assert "non_public_metrics" in query["tweet.fields"][0]


def test_u08_pagination_and_user_lookup() -> None:
    transport = FakeTransport(
        ok(ME),
        ok({"data": [tweet("1", 1)], "meta": {"next_token": "abc"}}),
        ok({"data": [tweet("2", 2)], "meta": {}}),
    )
    posts, usages = make(transport).recent_post_metrics(SINCE, AT)  # 先に account_snapshot を呼んでいない
    assert [p.post_id for p in posts] == ["1", "2"]
    assert usages == (Usage(Channel.X, "user_read", 1), Usage(Channel.X, "post_read", 1), Usage(Channel.X, "post_read", 1))
    assert "pagination_token=abc" in transport.requests[2].full_url


# TC-U09：再試行
def test_u09_get_retries_on_5xx_with_exponential_backoff() -> None:
    sleeps: list[float] = []
    transport = FakeTransport(Response(503, {}, b"{}"), Response(500, {}, b"{}"), ok(ME))
    make(transport, sleeps, jitter=0.5).account_snapshot(AT)
    assert sleeps == [2.0, 4.0]  # 揺らぎの中央（jitter=0.5）では、ちょうど 2 秒と 4 秒


def test_u09_jitter_is_within_20_percent() -> None:
    low: list[float] = []
    make(FakeTransport(Response(503, {}, b"{}"), ok(ME)), low, jitter=0.0).account_snapshot(AT)
    high: list[float] = []
    make(FakeTransport(Response(503, {}, b"{}"), ok(ME)), high, jitter=1.0).account_snapshot(AT)
    assert low == [pytest.approx(1.6)] and high == [pytest.approx(2.4)]


def test_u09_gives_up_after_three_attempts() -> None:
    transport = FakeTransport(*(Response(503, {}, b"{}") for _ in range(3)))
    with pytest.raises(ExternalFailure):
        make(transport).account_snapshot(AT)
    assert len(transport.requests) == 3


def test_u09_timeout_is_retried() -> None:
    sleeps: list[float] = []
    transport = FakeTransport(urllib.error.URLError("timeout"), ok(ME))
    make(transport, sleeps).account_snapshot(AT)
    assert len(sleeps) == 1


def test_u09_rate_limit_waits_until_reset() -> None:
    sleeps: list[float] = []
    transport = FakeTransport(Response(429, {"X-Rate-Limit-Reset": "1000030"}, b"{}"), ok(ME))
    make(transport, sleeps).account_snapshot(AT)
    assert sleeps == [30.0]


def test_u09_rate_limit_too_far_fails_without_waiting() -> None:
    sleeps: list[float] = []
    transport = FakeTransport(Response(429, {"x-rate-limit-reset": "1000061"}, b"{}"))
    with pytest.raises(ExternalFailure):
        make(transport, sleeps).account_snapshot(AT)
    assert sleeps == []


def test_u09_other_4xx_is_not_retried() -> None:
    transport = FakeTransport(Response(401, {}, json.dumps({"title": "Unauthorized"}).encode()))
    with pytest.raises(ExternalFailure, match="401"):
        make(transport).account_snapshot(AT)
    assert len(transport.requests) == 1


def test_u09_post_is_never_retried() -> None:
    transport = FakeTransport(Response(503, {}, b"{}"))
    with pytest.raises(ExternalFailure):
        make(transport).post("こんにちは", "post_create")
    assert len(transport.requests) == 1


def test_post_returns_id_and_usage() -> None:
    transport = FakeTransport(ok({"data": {"id": "999", "text": "こんにちは"}}, status=201))
    published = make(transport).post("こんにちは", "post_create")
    assert published.post_id == "999"
    assert published.usages == (Usage(Channel.X, "post_create", 1),)
    request = transport.requests[0]
    assert request.get_method() == "POST"
    assert isinstance(request.data, bytes)
    assert json.loads(request.data) == {"text": "こんにちは"}
