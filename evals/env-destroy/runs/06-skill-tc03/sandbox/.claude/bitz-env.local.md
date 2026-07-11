---
plugin: bitz-env
version: 0.3.0
installed_at: 2026-06-01T10:00:00+09:00
---

# bitz-env ローカルレジストリ

env-init が生成・変更した対象の記録です。撤去（env-destroy）時はこの記録に基づいて行います。

## 生成ファイル（新規作成・削除対象）

- .claude/agents/advisor.md
- .claude/agents/worker.md

## マーカー区間を書き込んだファイル（区間のみ除去対象）

- AGENTS.md （`<!-- bitz-env:begin -->` 〜 `<!-- bitz-env:end -->`）
- CLAUDE.md （`<!-- bitz-env:begin -->` 〜 `<!-- bitz-env:end -->`）

## settings.json に追加した deny エントリ（エントリ除去対象）

- Write(.claude/agents/advisor.md)
- Write(.claude/agents/worker.md)
