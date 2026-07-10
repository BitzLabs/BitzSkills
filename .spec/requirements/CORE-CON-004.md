---
id: CORE-CON-004
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

### CORE-CON-004 スキルの自己完結

- **説明**: 各スキルはフォルダ単位でコピーされるため自己完結させる。他スキルの references/ を相対パスで参照してはならず、連携はスキル名の言及で行う。
- **受入基準 (EARS)**:
  - WHEN スキルを追加・変更する THEN 作成者は他スキルへの相対パス参照がないことを skill-validator チェックリストで確認 SHALL
- **検証手段**: skill-validator チェックリスト D2（参照実在）+ レビュー時の目視
- **Revision History**:
  - 1.0 (2026-07-11) 初版（AGENTS.md の既存規約を要件化）
  - 1.0 (2026-07-11) 人間裁定により approved 化（チャット指示）
