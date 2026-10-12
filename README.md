# fukugyononuko-social

SNS（X、Threads など）の数字の取得と、承認つきの投稿をまとめて扱うシステム｜副業のぬこ

**状態：設計中。** 設計書は `docs/` に置く（要件 → 概要 → 基本 → 詳細 → テスト → トレーサビリティ表）。アーキテクチャは Juval Löwy『Righting Software』の The Method（変動性に基づく分解）に従う。

## 方針
- 本人が承認していない文章は投稿しない。
- 認証情報と、取得した数字・下書きはリポジトリに入れない。
- 道具：Python、uv、ruff、ty。

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
