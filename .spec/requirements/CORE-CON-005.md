---
id: CORE-CON-005
version: 1.0
status: approved
domain: governance
priority: high
origin: AGENTS.md（リポジトリ共通規約からの reverse-derived）
verification_method: manual-check
derived_from:
supersedes:
superseded_by:
confidence: high
---

### CORE-CON-005 プラグイン内スキル名の単一プレフィックス

- **説明**: 各プラグイン内のスキル名は単一プレフィックスで統一する（skill-* / sdd-* / ddd-* / plugin-*。2026-07-10 確定の命名規則）。
- **受入基準 (EARS)**:
  - WHEN 新しいスキルを追加する THEN 作成者はプラグインの既存プレフィックスに一致する name を付与 SHALL
- **検証手段**: PR レビュー + skill-validator チェックリスト B 群
- **Revision History**:
  - 1.0 (2026-07-11) 初版（AGENTS.md の既存規約を要件化）
  - 1.0 (2026-07-11) 人間裁定により approved 化（チャット指示）
