# bitz-env レジストリ

env-init による生成・変更の記録。env-destroy はこのファイルのみを根拠に撤去対象を判断する。

## 新規生成したファイル

- `.claude/agents/advisor.md` — 2026-07-12
- `.claude/agents/worker.md` — 2026-07-12
- `.claude/bitz-env.local.md` — 2026-07-12

## 既存ファイルへ書き込んだマーカー区間

- `AGENTS.md`（ガードレール節）: `<!-- bitz-env:begin -->` 〜 `<!-- bitz-env:end -->`（末尾に追記。既存9行は不変）
- `CLAUDE.md`（協調運用節）: `<!-- bitz-env:begin -->` 〜 `<!-- bitz-env:end -->`（末尾に追記。既存5行は不変）
- `.claude/settings.json`: permissions.deny/ask/allow をテンプレートとマージ（既存の "Bash(npm publish:*)" は保持）

## バックアップの有無

- git 管理下のため `.bak` は作成していない

## 割り当て

- 中心: Sonnet / advisor: Opus / worker: Haiku
