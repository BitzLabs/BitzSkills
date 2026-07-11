# bitz-env レジストリ

env-init による生成・変更の記録。env-destroy はこのファイルのみを根拠に撤去対象を判断する。

## 新規生成したファイル

- `.claude/agents/advisor.md` — 2026-07-11
- `.claude/agents/worker.md` — 2026-07-11

## 既存ファイルへ書き込んだマーカー区間

- `AGENTS.md`（ガードレール節）: `<!-- bitz-env:begin -->` 〜 `<!-- bitz-env:end -->`（既存内容の末尾に追加）
- `CLAUDE.md`（協調運用節）: `<!-- bitz-env:begin -->` 〜 `<!-- bitz-env:end -->`（既存内容の末尾に追加）
- `.claude/settings.json`: permissions.deny/ask/allow をテンプレートと和集合でマージ
  （既存 "Bash(npm publish:*)" は保持）

## バックアップの有無

- git 管理下のため `.bak` は作成していない

## 割り当て

- 中心: Sonnet / advisor: Opus / worker: Haiku
