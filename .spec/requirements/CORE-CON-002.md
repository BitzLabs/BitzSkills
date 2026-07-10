---
id: CORE-CON-002
version: 1.0
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

### CORE-CON-002 SKILL.md frontmatter の metadata 必須

- **説明**: 全スキルの SKILL.md frontmatter は name / description に加え、metadata（version / author / created / updated）を必須で持つ。内容変更時は semver で version を bump し updated を更新する。
- **受入基準 (EARS)**:
  - WHEN リリース前検証を実行する THEN システムは metadata 必須項目を欠く SKILL.md を FAIL として報告 SHALL
- **検証手段**: tests/test_release_check.py::test_release_check_missing_metadata、CI の release_check.py
- **Revision History**:
  - 1.0 (2026-07-11) 初版（AGENTS.md の既存規約を要件化）
  - 1.0 (2026-07-11) 人間裁定により approved 化（チャット指示）
