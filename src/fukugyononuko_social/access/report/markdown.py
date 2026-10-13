"""CMP-A05 ReportAccess の実装：運営者のノートに Markdown で書き出す（DD-11、EIF-05、02a §2a.3）。"""

import os
import tempfile
from pathlib import Path

from fukugyononuko_social.domain.channel import OPERATOR_TZ
from fukugyononuko_social.domain.metrics import Finished, MeasurementRun, Report, Running


def _cell(value: object) -> str:
    text = "―" if value is None else str(value)
    return text.replace("|", "｜").replace("\n", " ")


def _last_run(run: MeasurementRun | None) -> str:
    match run:
        case None:
            return "まだ計測していません"
        case Running(started_at=started):
            return f"{started.astimezone(OPERATOR_TZ):%Y-%m-%d %H:%M} に開始（終了の記録なし）"
        case Finished(finished_at=finished, outcome=outcome):
            return f"{finished.astimezone(OPERATOR_TZ):%Y-%m-%d %H:%M}：{outcome.value}"


def render(report: Report) -> str:
    lines = [
        "---",
        "type: metrics",
        f"updated: {report.generated_at.astimezone(OPERATOR_TZ):%Y-%m-%d}",
        "---",
        "# SNS の数字",
        "",
        "fukugyononuko-social（`nukosns measure`）が計測のたびに作り直す。手で編集しない。",
        "",
        "## 月ごと",
        "",
        "| 月 | チャネル | フォロワー | フォロー | その月の投稿 | 表示 | いいね"
        " | プロフィールのクリック | リンクのクリック | 費用（円） |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in report.monthly:
        cells = (r.month, r.channel.value, r.followers, r.following, r.posts_created)
        cells += (r.impressions, r.likes, r.profile_clicks, r.link_clicks, r.cost_jpy)
        lines.append("| " + " | ".join(_cell(c) for c in cells) + " |")
    lines += [
        "",
        "- 投稿の数字は、その月（日本時間）に作った投稿の合計。各投稿は最新の取得値を使う。",
        "- プロフィール・リンクのクリックは投稿から 30 日以内しか取れないため、それ以降は最後に取れた値のまま。",
        "",
        "## 直近 29 日の投稿（表示の多い順）",
        "",
        "| 日付 | チャネル | 表示 | いいね | プロフィールのクリック | 本文（冒頭） |",
        "|---|---|---|---|---|---|",
    ]
    for p in report.recent_posts:
        date = f"{p.created_at.astimezone(OPERATOR_TZ):%Y-%m-%d}"
        cells = (date, p.channel.value, p.impressions, p.likes, p.profile_clicks, p.text_head)
        lines.append("| " + " | ".join(_cell(c) for c in cells) + " |")
    lines += ["", "## 最後の計測", "", _last_run(report.last_run), ""]
    return "\n".join(lines)


class MarkdownReportAccess:
    def __init__(self, path: Path) -> None:
        self._path = path

    def publish_report(self, report: Report) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # 同じフォルダに一時ファイルを書いてから置き換える（書きかけを読ませない）
        fd, tmp = tempfile.mkstemp(dir=self._path.parent, prefix=".nukosns-", suffix=".md")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(render(report))
            os.replace(tmp, self._path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
