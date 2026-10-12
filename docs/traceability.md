# トレーサビリティ表

設計を変える PR では、この表も同じ PR で更新する。02 以降の ID（CC・DD・TC）は、各設計書を書くときに列を足す。

## 要件 → 構成要素

| 要件 | 上位 | 変動性 | 構成要素 | 状態 |
| --- | --- | --- | --- | --- |
| FR-01 アカウントの数字の取得 | BR-01 | VOL-01、VOL-03 | CMP-M01、CMP-A01、CMP-A02 | 初期 |
| FR-02 投稿ごとの数字の取得 | BR-01 | VOL-01、VOL-03 | CMP-M01、CMP-A01、CMP-A02 | 初期 |
| FR-03 時系列での保存 | BR-01 | VOL-09 | CMP-A02 | 初期 |
| FR-04 月ごとの集計と書き出し | BR-01 | VOL-04、VOL-10 | CMP-E01、CMP-A05 | 初期 |
| FR-05 週 1 回の自動実行 | BR-02 | VOL-08 | CMP-C02 | 初期 |
| FR-06 下書きの登録と検査 | BR-03、BR-04 | VOL-05、VOL-06 | CMP-C01、CMP-M02、CMP-E02、CMP-E03、CMP-A03 | 初期 |
| FR-07 承認済みの下書きだけを投稿 | BR-03 | VOL-07 | CMP-C01、CMP-M02、CMP-A03、CMP-A01 | 初期 |
| FR-08 投稿の結果の記録 | BR-01、BR-04 | VOL-09 | CMP-A03、CMP-A04 | 初期 |
| FR-09 費用の見積もり・記録・上限 | BR-04 | VOL-02、VOL-06 | CMP-E03、CMP-A04、CMP-A06 | 初期 |
| FR-10 複数チャネルへの投稿 | BR-02 | VOL-01 | CMP-M02、CMP-A01 | 将来 |
| FR-11 スマホからの承認 | BR-02 | VOL-07 | CMP-C03 | 将来 |
| FR-12 実行の記録をログに残す | BR-01、BR-02 | VOL-12 | CMP-U02 | 初期 |
| NFR-01 認証情報の扱い | BR-06 | VOL-11 | CMP-U01 | 初期 |
| NFR-02 データをリポジトリの外に置く | BR-06 | VOL-09 | CMP-A02、CMP-A03、CMP-A04（RES-03） | 初期 |
| NFR-03 公開リポジトリの禁止語の検査 | BR-03、BR-06 | ― | CI（`scripts/check_privacy.py`）、pre-commit フック | 初期 |
| NFR-04 送信直前の禁止語の検査 | BR-03 | VOL-05 | CMP-M02、CMP-E02、CMP-A06 | 初期 |
| NFR-05 計測の再実行で重複しない | BR-01 | VOL-04、VOL-09 | CMP-A02、CMP-E01 | 初期 |
| NFR-06 二重投稿をしない | BR-03、BR-04 | ― | CMP-M02、CMP-A03 | 初期 |
| NFR-07 月の費用の上限 | BR-04 | VOL-06 | CMP-E03、CMP-A06 | 初期 |
| NFR-08 部品の差し替えで変えられる | BR-05 | VOL-01、VOL-07〜VOL-12 | 全層（1.7 の変動性シナリオ） | 初期 |
| NFR-09 道具と、API を呼ばないテスト | BR-05 | ― | 全体 | 初期 |
| NFR-10 チャネルの規約 | BR-03 | VOL-01 | CMP-M02、CMP-A01（範囲：1.1） | 初期 |

## ユースケース → 構成要素

| UC | Manager | 流れ |
| --- | --- | --- |
| UC-01 週次の計測 | CMP-M01 | 01 §1.7 |
| UC-02 承認つきの投稿 | CMP-M02 | 01 §1.7 |
| UC-03 費用の確認 | CMP-M01 | 01 §1.7 |

## 逆引き：構成要素 → 要件

| 構成要素 | 要件 |
| --- | --- |
| CMP-C01 CLI | FR-06、FR-07 |
| CMP-C02 Scheduler | FR-05 |
| CMP-C03 承認アプリ（将来） | FR-11 |
| CMP-M01 MeasurementManager | FR-01、FR-02、UC-01、UC-03 |
| CMP-M02 PublishingManager | FR-06、FR-07、FR-10、NFR-04、NFR-06、NFR-10、UC-02 |
| CMP-E01 AggregationEngine | FR-04、NFR-05 |
| CMP-E02 DraftPolicyEngine | FR-06、NFR-04 |
| CMP-E03 CostEngine | FR-06、FR-09、NFR-07 |
| CMP-A01 ChannelAccess | FR-01、FR-02、FR-07、FR-10、NFR-10 |
| CMP-A02 MetricsAccess | FR-01〜FR-03、NFR-02、NFR-05 |
| CMP-A03 DraftAccess | FR-06〜FR-08、NFR-02、NFR-06 |
| CMP-A04 LedgerAccess | FR-08、FR-09、NFR-02 |
| CMP-A05 ReportAccess | FR-04 |
| CMP-A06 SettingsAccess | FR-09、NFR-04、NFR-07 |
| CMP-U01 Security | NFR-01 |
| CMP-U02 Logging | FR-12 |
| CMP-U03 Clock | NFR-09（時刻を固定したテスト） |
