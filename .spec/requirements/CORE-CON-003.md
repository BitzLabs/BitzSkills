---
id: CORE-CON-003
version: 1.1
status: approved
domain: governance
priority: high
origin: AGENTS.md（リポジトリ共通規約からの reverse-derived）
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### CORE-CON-003 marketplace.json と plugins/ 実体の双方向整合

- **説明**: Claude Code / Codex CLI が共有する .claude-plugin/marketplace.json の plugins[] と plugins/ ディレクトリ実体は双方向に一致しなければならない（未列挙の実体も、実体のない参照も許さない）。
- **受入基準 (EARS)**:
  - WHEN リリース前検証を実行する THEN システムは marketplace.json と plugins/ の不整合を FAIL として報告 SHALL
- **検証手段**: tests/test_release_check.py::test_release_check_ghost_plugin / test_release_check_unlisted_plugin、CI
- **Revision History**:
  - 1.0 (2026-07-11) 初版（AGENTS.md の既存規約を要件化）
  - 1.0 (2026-07-11) 人間裁定により approved 化（チャット指示）
  - 1.1 (2026-07-15) Codex CLI との互換カタログ共有を明記
