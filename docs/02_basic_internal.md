# 2b. 基本設計（内部）

## 2b.1 構成要素の契約

操作は業務の言葉で表す（01 §1.6 規則 7）。型の詳細は 03 で決める。

| 構成要素 | 操作 | 内容 |
| --- | --- | --- |
| CMP-M01 MeasurementManager | `measure()` | UC-01 を 1 回実行し、結果（成功・失敗、件数、費用）を返す |
| | `cost_status(month)` | UC-03。その月（省略すると今月）の費用の合計・上限・残り |
| CMP-M02 PublishingManager | `register_draft(channel, text)` | 検査と見積もりをして下書きを保存し、番号・指紋・検査の結果を返す |
| | `drafts(status)`、`draft(id)`、`discard(id)` | 下書きの一覧・詳細・破棄 |
| | `approve(id, fingerprint)` | 指紋が一致すれば承認を記録する |
| | `publish(id)` | 承認済みの下書きを再検査し、上限を確かめて投稿し、結果と費用を記録する |
| CMP-E01 AggregationEngine | `summarize(now)` | 保存された時系列（A02）と費用の記録（A04）から、月ごとの集計と直近の投稿の一覧を作る。各投稿は最新の取得値だけを使い、各月のアカウントの数字はその月の最後の取得値を使う（NFR-05） |
| CMP-E02 DraftPolicyEngine | `review(channel, text)` | 検査の結果（不合格の理由と注意の一覧）を返す。初期のルール：文字数（X は重みつき 280）、禁止語、URL の有無（あれば注意として費用の差を示す） |
| CMP-E03 CostEngine | `estimate(usage)` | 課金される操作の一覧（チャネル、操作、件数）をドルと円に換算する |
| | `afford(cost, month)` | 今月の合計にこの費用を足しても上限以内かを判定する |
| | `status(month)` | 今月の合計・上限・残り |
| CMP-A01 ChannelAccess | `account_snapshot()` | アカウントの数字（共通の項目名）と、課金された操作 |
| | `recent_post_metrics(since, may_spend)` | 直近の投稿ごとの数字（共通の項目名）と、課金された操作。ページを取る前に、そのページの上限の費用を `may_spend` で確かめ、許されなければ止める（DD-09） |
| | `post(text, operation)` | 投稿し、投稿 ID と課金された操作を返す。operation は費用の操作の名前（DD-20） |
| | `usage_upper_bound()` | 計測 1 回分の、課金される操作の上限（実行前の見積もりに使う） |
| CMP-A02 MetricsAccess | `record(snapshot)`、`history(since)` | 取得した数字を時刻つきで保存する／読み出す |
| CMP-A03 DraftAccess | `save_draft`、`find`、`list`、`record_approval`、`mark_sending`、`record_published`、`record_failed`、`discard` | 下書きの状態の遷移（02a §2a.1）を保存する。不正な遷移は拒否する |
| CMP-A04 LedgerAccess | `record_charge(charge)`、`month_total(month)` | 費用の記録と、月の合計 |
| CMP-A05 ReportAccess | `publish_report(report)` | 集計を書き出し先に書く（全体を置き換える） |
| CMP-A06 SettingsAccess | `price_table()`、`budget()`、`denylist()` | 単価表、為替と上限、禁止語 |
| CMP-A07 TransactionAccess | `atomically()` | この中の保存先への書き込みを、まとめて確定する。途中で失敗したら、どれも確定しない（DD-21） |
| CMP-U01 Security | `credential(channel, name)` | 認証情報を返す。値を文字列表現やログに出さない型で包む |
| CMP-U02 Logging | `record(event)`、`recent(n)` | 実行の記録を 1 件残す／最後の n 件を読む |
| CMP-U03 Clock | `now()` | 現在時刻（UTC） |

## 2b.2 コールチェーン（CC）

| ID | UC | 呼び出しの順 |
| --- | --- | --- |
| CC-01 | UC-01 週次の計測 | C02 → M01.measure → A01.usage_upper_bound → E03.estimate → E03.afford（超えるなら記録して終了）→ A01.account_snapshot → A01.recent_post_metrics（ページごとに E03.afford）→ A07.atomically（A02.record、E03.estimate（実際の課金）→ A04.record_charge）→ E01.summarize（A02.history、A04 の月ごとの合計）→ A05.publish_report → U02.record |
| CC-02 | UC-02 登録 | C01 → M02.register_draft → E02.review（A06.denylist）→ E03.estimate → A03.save_draft（合格なら「下書き」、不合格なら「不合格」）→ U02.record |
| CC-03 | UC-02 承認 | 運営者 → C01 → M02.approve → A03.find → 指紋の照合 → A03.record_approval → U02.record |
| CC-04 | UC-02 投稿 | C01 → M02.publish → A03.find（「承認済み」か「失敗」だけ）→ 指紋の再照合 → E02.review（送信直前の再検査、NFR-04）→ E03.estimate → E03.afford → A03.mark_sending → A01.post → A07.atomically（A03.record_published、A04.record_charge）（失敗なら record_failed）→ U02.record |
| CC-05 | UC-03 費用の確認 | C01 → M01.cost_status → E03.status（A04.month_total、A06.budget） |

- CC-01 で取得の途中に失敗したら、取れた分だけ保存し、集計は前回のまま残して、失敗を記録する（FR-12）。チャネルが 2 つ以上なら、失敗したチャネルがあっても残りのチャネルは続ける（DD-19）。
- CC-04 で「送信中」にしてから投稿する。投稿の直後に落ちても、再送で二重に投稿しない（NFR-06）。

## 2b.3 共通の項目名（VOL-03）

チャネル固有の名前は CMP-A01 の中で、次の共通の名前に揃える。

| 共通の名前 | 意味 | X での名前 |
| --- | --- | --- |
| followers | フォロワー | `followers_count` |
| following | フォロー | `following_count` |
| posts | 投稿数 | `tweet_count` |
| impressions | 表示 | `impression_count` |
| likes | いいね | `like_count` |
| replies | 返信 | `reply_count` |
| reposts | リポスト | `retweet_count` |
| quotes | 引用 | `quote_count` |
| bookmarks | ブックマーク | `bookmark_count` |
| profile_clicks | プロフィールのクリック | `user_profile_clicks` |
| link_clicks | リンクのクリック | `url_link_clicks` |
