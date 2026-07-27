---
id: CORE-CON-001
version: 1.1
status: verified
domain: governance
priority: high
origin: AGENTS.md（リポジトリ共通規約からの reverse-derived）
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### CORE-CON-001 3マニフェストの version 同値

- **説明**: 各プラグインは Claude Code 用（.claude-plugin/plugin.json）、Antigravity 2.0 用（plugin.json）、Codex CLI 用（.codex-plugin/plugin.json）の3マニフェストを持ち、version は常に同じ値でなければならない。
- **受入基準 (EARS)**:
  - WHEN プラグインの version を変更する THEN システムは bump_version.py により3つのマニフェストを同値に更新 SHALL
- **検証手段**: tests/test_bump_version.py（同値性・原子性）と tests/test_release_check.py（不一致で FAIL）、CI の release_check.py
- **Revision History**:
  - 1.0 (2026-07-11) 初版（AGENTS.md の既存規約を要件化）
  - 1.0 (2026-07-11) 人間裁定により approved 化（チャット指示）
  - 1.1 (2026-07-15) Codex CLI 用マニフェストを同期対象へ追加
