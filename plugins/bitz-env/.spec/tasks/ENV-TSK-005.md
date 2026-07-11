---
implements: [ENV-FR-008]
depends_on: []
boundary: plugins/bitz-env/hooks/hooks.json, plugins/bitz-env/rules/00-guardrails.md, tests/test_env_guard.py
status: done
---

### rules/*.md の Claude Code 向け SessionStart 注入

- **作業内容**: hooks/hooks.json に SessionStart フックを追加し、
  `cat "${CLAUDE_PLUGIN_ROOT}"/rules/*.md` でルール文書をコンテキストへ注入する。
  rules/00-guardrails.md の表題を両プラットフォーム共通に改める。
  注入コマンドの出力を検証する pytest を追加する。
- **実施記録**: 2026-07-11 実施（v0.2.0）。
- **備考**: 要検証項目#2（Claude Code の rules/ 挙動）の設計解決。
  実環境での注入確認（インストール後）は残タスク。
