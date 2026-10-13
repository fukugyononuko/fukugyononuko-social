"""CMP-A01 ChannelAccess の X の実装（EIF-01、DD-09）。

- 認証は OAuth 1.0a のユーザーコンテキスト（本人だけの数字と投稿に必要）。
- GET は 429・5xx・タイムアウトで最大 2 回、指数バックオフ（2 秒、4 秒、±20%）で再試行する。
- POST（投稿）は再試行しない（二重投稿を防ぐ。NFR-06）。投稿されたかわからない失敗は UncertainPost にする。
- 取得の途中の失敗は、それまでの課金と投稿を PartialFetch で持ち帰る。
- チャネル固有の名前は、共通の項目名（02b §2b.3）に揃える。
"""

import json
import random
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fukugyononuko_social.access.channels import _oauth1
from fukugyononuko_social.domain.channel import Channel
from fukugyononuko_social.domain.drafts import PublishedPost
from fukugyononuko_social.domain.errors import ExternalFailure, UncertainPost
from fukugyononuko_social.domain.metrics import AccountSnapshot, PartialFetch, PostMetrics
from fukugyononuko_social.domain.money import Usage
from fukugyononuko_social.utilities.security import Security

API = "https://api.x.com/2"
TIMEOUT = 30
MAX_ATTEMPTS = 3
BASE_WAIT = 2.0
JITTER = 0.2
MAX_RATE_LIMIT_WAIT = 60
TEXT_HEAD = 60
POSTS_PER_PAGE = 100


@dataclass(frozen=True)
class Response:
    status: int
    headers: Mapping[str, str]
    body: bytes


type Transport = Callable[[urllib.request.Request], Response]


def urllib_transport(request: urllib.request.Request) -> Response:
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as r:
            return Response(r.status, dict(r.headers), r.read())
    except urllib.error.HTTPError as e:
        return Response(e.code, dict(e.headers), e.read())


class XChannelAccess:
    def __init__(
        self,
        security: Security,
        transport: Transport = urllib_transport,
        sleep: Callable[[float], None] = time.sleep,
        jitter: Callable[[], float] = random.random,
        epoch: Callable[[], float] = time.time,
    ) -> None:
        self._security = security
        self._transport = transport
        self._sleep = sleep
        self._jitter = jitter
        self._epoch = epoch
        self._user_id: str | None = None

    @property
    def channel(self) -> Channel:
        return Channel.X

    # ---- 契約の操作 ----

    def account_snapshot(self, at: datetime) -> tuple[AccountSnapshot, tuple[Usage, ...]]:
        data = self._get("/users/me", {"user.fields": "public_metrics"})["data"]
        self._user_id = data["id"]
        m = data["public_metrics"]
        snapshot = AccountSnapshot(Channel.X, at, m["followers_count"], m["following_count"], m["tweet_count"])
        return snapshot, (Usage(Channel.X, "user_read", 1),)

    def recent_post_metrics(self, since: datetime, at: datetime) -> tuple[tuple[PostMetrics, ...], tuple[Usage, ...]]:
        usages: list[Usage] = []
        if self._user_id is None:
            _, first = self.account_snapshot(at)
            usages += first
        params = {
            "max_results": str(POSTS_PER_PAGE),
            "start_time": since.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "exclude": "retweets",
            "tweet.fields": "created_at,public_metrics,non_public_metrics",
        }
        posts: list[PostMetrics] = []
        while True:
            try:
                page = self._get(f"/users/{self._user_id}/tweets", params)
            except ExternalFailure as e:
                # 成功したページの課金と投稿を持ち帰る（DD-09）
                raise PartialFetch(str(e), usages=tuple(usages), posts=tuple(posts)) from e
            items = page.get("data", [])
            posts += [_post_metrics(t, at) for t in items]
            if items:
                usages.append(Usage(Channel.X, "post_read", len(items)))
            token = page.get("meta", {}).get("next_token")
            if not token:
                return tuple(posts), tuple(usages)
            params["pagination_token"] = token

    def post(self, text: str, operation: str) -> PublishedPost:
        try:
            response = self._send("POST", "/tweets", {}, json.dumps({"text": text}).encode())
        except (urllib.error.URLError, TimeoutError) as e:
            raise UncertainPost("X からの応答がないまま終わりました。投稿されたかどうかわかりません") from e
        if response.status >= 500:
            raise UncertainPost(f"X が投稿の途中でエラーを返しました（{response.status}）。投稿されたかどうかわかりません")
        if response.status not in (200, 201):
            raise ExternalFailure(f"X への投稿に失敗しました（{response.status}）：{_detail(response)}")
        post_id = json.loads(response.body)["data"]["id"]
        return PublishedPost(Channel.X, post_id, (Usage(Channel.X, operation, 1),))

    def usage_upper_bound(self) -> tuple[Usage, ...]:
        return (Usage(Channel.X, "user_read", 1), Usage(Channel.X, "post_read", POSTS_PER_PAGE))

    # ---- 内部 ----

    def _get(self, path: str, params: Mapping[str, str]) -> dict[str, Any]:
        last_status = 0
        for attempt in range(MAX_ATTEMPTS):
            final = attempt == MAX_ATTEMPTS - 1
            try:
                response = self._send("GET", path, params, None)
            except (urllib.error.URLError, TimeoutError) as e:
                if final:
                    raise ExternalFailure(f"X に接続できません：{path}") from e
                self._sleep(self._backoff(attempt))
                continue
            if response.status == 200:
                return json.loads(response.body)
            last_status = response.status
            if response.status != 429 and response.status < 500:
                raise ExternalFailure(f"X API のエラー（{response.status}）：{path}：{_detail(response)}")
            if final:
                break
            self._sleep(self._wait_for(response, attempt))
        raise ExternalFailure(f"X API が {MAX_ATTEMPTS} 回とも失敗しました（{last_status}）：{path}")

    def _backoff(self, attempt: int) -> float:
        return BASE_WAIT * (2**attempt) * (1 - JITTER + 2 * JITTER * self._jitter())

    def _wait_for(self, response: Response, attempt: int) -> float:
        reset = {k.lower(): v for k, v in response.headers.items()}.get("x-rate-limit-reset")
        if response.status == 429 and reset is not None:
            wait = float(reset) - self._epoch()
            if wait > MAX_RATE_LIMIT_WAIT:
                raise ExternalFailure(f"X の利用制限が {int(wait)} 秒後まで解けません。時間をおいて実行してください")
            return max(wait, 0.0)
        return self._backoff(attempt)

    def _send(self, method: str, path: str, params: Mapping[str, str], body: bytes | None) -> Response:
        url = API + path
        oauth = {
            "oauth_consumer_key": self._security.credential(Channel.X, "api-key").reveal(),
            "oauth_nonce": secrets.token_hex(16),
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp": str(int(self._epoch())),
            "oauth_token": self._security.credential(Channel.X, "access-token").reveal(),
            "oauth_version": "1.0",
        }
        sig = _oauth1.signature(
            method,
            url,
            params,
            oauth,
            self._security.credential(Channel.X, "api-key-secret").reveal(),
            self._security.credential(Channel.X, "access-token-secret").reveal(),
        )
        headers = {"Authorization": _oauth1.header(oauth, sig)}
        if body is not None:
            headers["Content-Type"] = "application/json"
        query = "?" + urllib.parse.urlencode(params) if params else ""
        return self._transport(urllib.request.Request(url + query, data=body, headers=headers, method=method))


def _post_metrics(t: Mapping[str, Any], at: datetime) -> PostMetrics:
    pub = t.get("public_metrics", {})
    priv = t.get("non_public_metrics", {})
    return PostMetrics(
        channel=Channel.X,
        post_id=t["id"],
        created_at=datetime.fromisoformat(t["created_at"].replace("Z", "+00:00")),
        fetched_at=at,
        text_head=t.get("text", "").replace("\n", " ")[:TEXT_HEAD],
        impressions=pub.get("impression_count"),
        likes=pub.get("like_count"),
        replies=pub.get("reply_count"),
        reposts=pub.get("retweet_count"),
        quotes=pub.get("quote_count"),
        bookmarks=pub.get("bookmark_count"),
        profile_clicks=priv.get("user_profile_clicks"),
        link_clicks=priv.get("url_link_clicks"),
    )


def _detail(response: Response) -> str:
    """エラーの応答から、短い説明だけを取り出す（認証情報は応答に含まれない）。"""
    try:
        data = json.loads(response.body)
        return str(data.get("detail") or data.get("title") or data)[:200]
    except ValueError, AttributeError:
        return response.body[:200].decode(errors="replace")
