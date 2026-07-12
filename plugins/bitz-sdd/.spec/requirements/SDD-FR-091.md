---
id: SDD-FR-091
version: 1.0
status: approved
domain: verification
priority: medium
origin: skills/sdd-test/SKILL.md v0.1.0（reverse-derived）
verification_method: manual-check
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-091 テスト仕様書の定型記録

- **説明**: sdd-test は導出したテストの実装後、要件との対応と検証ステータスを示すテスト仕様書を指定の場所にフォーマットに従って保存しなければならない（公開契約に該当）。
- **受入基準 (EARS)**:
  - WHEN テストを実装した THEN sdd-test はテスト仕様書を定型フォーマットで `.spec/specs/<feature>/` 配下に記録 SHALL
- **検証手段**: SKILL.md / references の目視確認 + skill-validator チェックリスト
- **Revision History**:
  - 1.0 (2026-07-12) 初版（実装 v0.1.0 からの reverse-derived。ワークスペース新設に伴う逆起票）
  - 1.0 (2026-07-12) 人間裁定により approved 化（チャット指示）
