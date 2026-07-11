# bitz-env レジストリ

env-init による生成・変更の記録。env-destroy はこのファイルのみを根拠に撤去対象を判断する。

## 新規生成したファイル

- `.claude/settings.json` — 2026-07-11
- `AGENTS.md` — 2026-07-11
- `CLAUDE.md` — 2026-07-11
- `.claude/agents/advisor.md` — 2026-07-11
- `.claude/agents/worker.md` — 2026-07-11

## 既存ファイルへ書き込んだマーカー区間

- `AGENTS.md`（ガードレール節）: `<!-- bitz-env:begin -->` 〜 `<!-- bitz-env:end -->`（新規作成のため全体がマーカー区間管理下）
- `CLAUDE.md`（協調運用節）: `<!-- bitz-env:begin -->` 〜 `<!-- bitz-env:end -->`（新規作成のため全体がマーカー区間管理下）

## バックアップの有無

- git 管理下のため `.bak` は作成していない

## 割り当て

- 中心: Sonnet / advisor: Opus / worker: Haiku
