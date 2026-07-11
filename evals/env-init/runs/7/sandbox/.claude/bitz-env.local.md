# bitz-env レジストリ

env-init による生成・変更の記録。env-destroy はこのファイルのみを根拠に撤去対象を判断する。

## 新規生成したファイル

- `.claude/settings.json` — 2026-07-12
- `AGENTS.md` — 2026-07-12
- `.claude/agents/advisor.md` — 2026-07-12
- `.claude/agents/worker.md` — 2026-07-12

## 既存ファイルへ書き込んだマーカー区間

- `CLAUDE.md`（協調運用節）: `<!-- bitz-env:begin -->` 〜 `<!-- bitz-env:end -->`（末尾に追記。既存5行は不変）

## バックアップの有無

- `CLAUDE.md.bak`（git 管理外のため、CLAUDE.md 書き換え前に作成）

## 割り当て

- 中心: Sonnet / advisor: Opus / worker: Haiku

## 案内事項（未実行）

- 対象フォルダが git 管理外だったため `git init` の実行を案内した。
  ユーザー確認が得られていないため、本ツールからは実行していない。
