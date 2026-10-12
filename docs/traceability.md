# トレーサビリティ表

設計を変える PR では、この表も同じ PR で更新する。

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

## 要件 → 基本設計（02）

| 要件 | コマンド・外部インターフェース | コールチェーン |
| --- | --- | --- |
| FR-01、FR-02 | CLI-07、EIF-01 | CC-01 |
| FR-03 | EIF-02 | CC-01 |
| FR-04 | EIF-05 | CC-01 |
| FR-05 | EIF-08 | CC-01 |
| FR-06 | CLI-01〜CLI-04 | CC-02 |
| FR-07 | CLI-05、CLI-06、EIF-09 | CC-03、CC-04 |
| FR-08 | CLI-06 | CC-04 |
| FR-09 | CLI-08、EIF-03 | CC-01、CC-04、CC-05 |
| FR-12 | CLI-09、EIF-07 | CC-01〜CC-04 |
| NFR-01 | EIF-06 | ― |
| NFR-02 | EIF-02、EIF-03 | ― |
| NFR-04 | EIF-04 | CC-02、CC-04 |
| NFR-05 | ― | CC-01（CMP-E01 は投稿ごとに最新の値だけを使う） |
| NFR-06 | 下書きの状態（02a §2a.1） | CC-04 |
| NFR-07 | EIF-03 | CC-01、CC-04 |
| NFR-10 | EIF-01 | CC-04 |

## 要件 → 詳細設計（03）・テスト（04）

| 要件 | 詳細設計 | テスト |
| --- | --- | --- |
| FR-01、FR-02 | DD-02、DD-09 | TC-U08、TC-U09、TC-I01 |
| FR-03 | DD-03 | TC-I01、TC-I03 |
| FR-04 | DD-10、DD-11 | TC-U06、TC-S03 |
| FR-05 | DD-16 | （手動で確認：launchd の読み込み） |
| FR-06 | DD-04〜DD-07 | TC-U01〜TC-U03、TC-I04 |
| FR-07 | DD-02、DD-04、DD-05、DD-17 | TC-U10、TC-U11、TC-U14、TC-I05、TC-I06、TC-S01 |
| FR-08 | DD-03、DD-04 | TC-I07 |
| FR-09 | DD-08、DD-12 | TC-U04、TC-U05、TC-I02、TC-I08 |
| FR-12 | DD-14 | TC-I02、TC-I03、TC-N02 |
| NFR-01 | DD-13 | TC-U12、TC-N02 |
| NFR-02 | DD-03、DD-12 | TC-N03 |
| NFR-03 | ― | TC-N01、TC-N04 |
| NFR-04 | DD-07 | TC-U03、TC-I06 |
| NFR-05 | DD-03、DD-09、DD-10 | TC-U06、TC-U13 |
| NFR-06 | DD-04、DD-09 | TC-U09、TC-U10、TC-I07 |
| NFR-07 | DD-08 | TC-U05、TC-I02、TC-R03 |
| NFR-08 | DD-01、DD-15 | TC-A02、TC-R01〜TC-R03 |
| NFR-09 | DD-01 | TC-A01、TC-A03、全テスト（ネットワーク禁止） |
| NFR-10 | DD-09、DD-17 | TC-I06 |
| 利用規則（01 §1.6） | DD-01 | TC-A01、TC-A02 |

## ユースケース → 構成要素

| UC | Manager | 流れ |
| --- | --- | --- |
| UC-01 週次の計測 | CMP-M01 | CC-01 |
| UC-02 承認つきの投稿 | CMP-M02 | CC-02、CC-03、CC-04 |
| UC-03 費用の確認 | CMP-M01 | CC-05 |

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
