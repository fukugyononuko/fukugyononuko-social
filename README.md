# fukugyononuko-social

SNS（X、Threads など）の数字の取得と、承認つきの投稿をまとめて扱うシステム｜副業のぬこ

**状態：運用中（X のみ）。** 週 1 回の計測と、承認つきの投稿が動いている。設計書は `docs/` に置く（要件 → 概要 → 基本 → 詳細 → テスト → トレーサビリティ表）。アーキテクチャは Juval Löwy『Righting Software』の The Method（変動性に基づく分解）に従う。

## 方針
- 本人が承認していない文章は投稿しない。
- 認証情報と、取得した数字・下書きはリポジトリに入れない。
- 道具：Python、uv、ruff、ty。

## 使い方

| コマンド | 内容 |
| --- | --- |
| `nukosns measure` | 計測を 1 回実行する（定期実行もこれを呼ぶ） |
| `nukosns cost [--month YYYY-MM]` | 月の費用の合計・上限・残り |
| `nukosns draft add --channel x --text TEXT` | 下書きを登録する（検査と費用の見積もり） |
| `nukosns draft list` / `show ID` / `discard ID` | 下書きの一覧・詳細・破棄 |
| `nukosns approve ID 指紋` | 承認する。**運営者だけ**が実行する（Claude Code からは止める） |
| `nukosns publish ID` | 承認済みの下書きを投稿する |
| `nukosns log [--tail N]` | 実行の記録 |

詳しくは [docs/02_basic_external.md](docs/02_basic_external.md)。

## セットアップ（macOS）

1. コマンドを入れる：`uv tool install --editable .`（`~/.local/bin/nukosns`。[DD-16](docs/03_detailed.md#dd-16-定期実行cmp-c02eif-08)）
2. 設定を置く：`settings.example.toml` を `~/fukugyononuko/data/fukugyononuko-social/settings.toml` に写す（[DD-12](docs/03_detailed.md#dd-12-設定cmp-a06eif-03)）
3. 認証情報を macOS キーチェーンに入れる：アカウント `fukugyononuko`、サービス `x-api-key`・`x-api-key-secret`・`x-access-token`・`x-access-token-secret`（[EIF-06](docs/02_basic_external.md#2a2-外部インターフェースeif)）
4. 定期実行を登録する：`uv run python scripts/install_launchd.py`（毎週月曜 9:00。雛形は [deploy/launchd/](deploy/launchd/)）
5. 承認の制限：Claude Code の `.claude/settings.json` に、禁止ルールと hook（[deploy/claude/block_approve.py](deploy/claude/block_approve.py)）を入れる（[DD-17](docs/03_detailed.md#dd-17-承認の制限eif-09)）

## 開発

```sh
uv sync
uv run ruff check . && uv run ruff format --check .
uv run ty check
uv run pytest
python3 scripts/check_privacy.py   # 禁止語は git 管理外の .privacy-denylist から読む
```

## ライセンス
MIT
