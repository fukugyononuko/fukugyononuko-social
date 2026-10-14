"""CMP-C01 CLI の実装：argparse と表示（CLI-01〜CLI-09、DD-15）。

例外を終了コードに変える：BusinessRejection → 1、UsageError → 2、ExternalFailure → 3。
"""

import argparse
import re
import sys
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path
from typing import assert_never

from fukugyononuko_social.clients.cli import App
from fukugyononuko_social.domain.channel import OPERATOR_TZ, Channel
from fukugyononuko_social.domain.drafts import (
    Approved,
    Discarded,
    Draft,
    DraftStatus,
    Failed,
    Finding,
    Pending,
    Published,
    Rejected,
    Sending,
)
from fukugyononuko_social.domain.errors import BusinessRejection, ExternalFailure, UsageError

OK, REJECTED, USAGE, EXTERNAL = 0, 1, 2, 3
SHORT_FINGERPRINT = 8
HEAD = 30
_MONTH = re.compile(r"\d{4}-(0[1-9]|1[0-2])")


def run(argv: Sequence[str] | None, build: Callable[[], App]) -> int:
    parser = _parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:  # argparse の誤り（2）と --help（0）
        return e.code if isinstance(e.code, int) else USAGE
    try:
        return args.handler(build(), args)
    except BusinessRejection as e:
        return _fail(REJECTED, e)
    except UsageError as e:
        return _fail(USAGE, e)
    except ExternalFailure as e:
        return _fail(EXTERNAL, e)


def _fail(code: int, e: Exception) -> int:
    print(f"エラー：{e}", file=sys.stderr)
    return code


# ---- コマンド ----


def _draft_add(app: App, args: argparse.Namespace) -> int:
    text = args.text if args.text is not None else _read(args.file)
    draft = app.publishing.register_draft(Channel(args.channel), text)
    print(_detail(draft))
    return REJECTED if draft.status is DraftStatus.REJECTED else OK


def _draft_list(app: App, args: argparse.Namespace) -> int:
    drafts = app.publishing.drafts(DraftStatus(args.status) if args.status else None)
    if not drafts:
        print("下書きはありません")
    for d in drafts:
        head = d.text.replace("\n", " ")
        head = head if len(head) <= HEAD else head[:HEAD] + "…"
        print(f"#{d.id}\t{d.status.label}\t{d.channel.value}\t{_time(d.created_at)}\t{head}")
    return OK


def _draft_show(app: App, args: argparse.Namespace) -> int:
    print(_detail(app.publishing.draft(args.id)))
    return OK


def _draft_discard(app: App, args: argparse.Namespace) -> int:
    d = app.publishing.discard(args.id)
    print(f"#{d.id} を破棄しました")
    return OK


def _approve(app: App, args: argparse.Namespace) -> int:
    d = app.publishing.approve(args.id, args.fingerprint)
    print(f"#{d.id} を承認しました。投稿するには：nukosns publish {d.id}")
    return OK


def _publish(app: App, args: argparse.Namespace) -> int:
    d = app.publishing.publish(args.id)
    match d.state:
        case Published(post_id=post_id):
            print(f"#{d.id} を投稿しました（投稿 ID：{post_id}、費用 {d.estimate.jpy} 円の見積もり）")
        case _:
            print(_detail(d))
    return OK


def _measure(app: App, args: argparse.Namespace) -> int:
    s = app.measurement.measure()
    print(f"計測しました：アカウント {s.accounts} 件、投稿 {s.posts} 件、費用 {s.cost_jpy} 円")
    return OK


def _cost(app: App, args: argparse.Namespace) -> int:
    if args.month is not None and not _MONTH.fullmatch(args.month):
        raise UsageError(f"月は YYYY-MM の形で指定してください：{args.month}")
    s = app.measurement.cost_status(args.month)
    print(f"{s.month}：使用 {s.spent_jpy} 円 / 上限 {s.cap_jpy} 円（残り {s.remaining_jpy} 円）")
    return OK


def _log(app: App, args: argparse.Namespace) -> int:
    lines = app.log.recent(args.tail)
    print("\n".join(lines) if lines else "記録はありません")
    return OK


# ---- 表示 ----


def _detail(d: Draft) -> str:
    short = d.fingerprint[:SHORT_FINGERPRINT]
    lines = [
        f"#{d.id} {d.status.label}（{d.channel.value}）",
        f"作成：{_time(d.created_at)}（日本時間）",
        f"指紋：{short}",
        f"見積もり：{d.estimate.jpy} 円（${d.estimate.usd}）",
    ]
    lines += [f"注意：{w.message}" for w in d.warnings]
    lines += _state_lines(d)
    lines += ["----", d.text, "----"]
    if d.status is DraftStatus.PENDING:
        lines += ["文章を確かめてから、承認するときは次を実行してください：", f"  ! nukosns approve {d.id} {short}"]
    return "\n".join(lines)


def _state_lines(d: Draft) -> list[str]:
    match d.state:
        case Rejected(errors=errors):
            return [f"不合格の理由：{_messages(errors)}"]
        case Pending() | Discarded():
            return []
        case Approved(approved_at=at) | Sending(approved_at=at):
            return [f"承認：{_time(at)}"]
        case Published(approved_at=at, post_id=post_id, published_at=published_at):
            return [f"承認：{_time(at)}", f"投稿：{_time(published_at)}（投稿 ID：{post_id}）"]
        case Failed(approved_at=at, error=error):
            return [f"承認：{_time(at)}", f"失敗：{error}"]
        case _:
            assert_never(d.state)


def _messages(findings: tuple[Finding, ...]) -> str:
    return "／".join(f.message for f in findings)


def _time(moment: datetime) -> str:
    return moment.astimezone(OPERATOR_TZ).strftime("%Y-%m-%d %H:%M")


def _read(path: str) -> str:
    try:
        return Path(path).expanduser().read_text(encoding="utf-8")
    except OSError as e:
        raise UsageError(f"下書きのファイルを読めません：{path}") from e


def _positive(value: str) -> int:
    n = int(value)
    if n <= 0:
        raise argparse.ArgumentTypeError("1 以上の整数で指定してください")
    return n


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="nukosns", description="SNS の数字の取得と、承認つきの投稿")
    sub = p.add_subparsers(dest="command", required=True)

    draft = sub.add_parser("draft", help="下書き").add_subparsers(dest="draft_command", required=True)
    add = draft.add_parser("add", help="下書きを登録する（CLI-01）")
    add.add_argument("--channel", required=True, choices=[c.value for c in Channel])
    source = add.add_mutually_exclusive_group(required=True)
    source.add_argument("--text")
    source.add_argument("--file")
    add.set_defaults(handler=_draft_add)
    lst = draft.add_parser("list", help="下書きの一覧（CLI-02）")
    lst.add_argument("--status", choices=[s.value for s in DraftStatus])
    lst.set_defaults(handler=_draft_list)
    show = draft.add_parser("show", help="下書きの詳細（CLI-03）")
    show.add_argument("id", type=_positive)
    show.set_defaults(handler=_draft_show)
    discard = draft.add_parser("discard", help="下書きを破棄する（CLI-04）")
    discard.add_argument("id", type=_positive)
    discard.set_defaults(handler=_draft_discard)

    approve = sub.add_parser("approve", help="下書きを承認する。運営者だけが実行する（CLI-05）")
    approve.add_argument("id", type=_positive)
    approve.add_argument("fingerprint")
    approve.set_defaults(handler=_approve)
    publish = sub.add_parser("publish", help="承認済みの下書きを投稿する（CLI-06）")
    publish.add_argument("id", type=_positive)
    publish.set_defaults(handler=_publish)
    sub.add_parser("measure", help="計測を 1 回実行する（CLI-07）").set_defaults(handler=_measure)
    cost = sub.add_parser("cost", help="月の費用（CLI-08）")
    cost.add_argument("--month")
    cost.set_defaults(handler=_cost)
    log = sub.add_parser("log", help="実行の記録（CLI-09）")
    log.add_argument("--tail", type=_positive, default=20)
    log.set_defaults(handler=_log)
    return p
