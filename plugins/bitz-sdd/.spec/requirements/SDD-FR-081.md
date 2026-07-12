---
id: SDD-FR-081
version: 1.0
status: draft
domain: execution
priority: high
origin: skills/sdd-git/SKILL.md v0.1.0（reverse-derived）
verification_method: manual-check
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-081 実装コミットの Implements フッター宣言

- **説明**: sdd-git は要件を実装したコミットを作成する際、機械検証（spec_inspect.py の implements マップ突合）を可能にするため、コミットメッセージに対象要件 ID を示すフッターを含めなければならない（公開契約に該当）。
- **受入基準 (EARS)**:
  - WHEN 実装コミットを作成する THEN sdd-git はコミットメッセージのフッターに `Implements: <要件ID>` を宣言 SHALL
- **検証手段**: SKILL.md / references の目視確認 + skill-validator チェックリスト
- **Revision History**:
  - 1.0 (2026-07-12) 初版（実装 v0.1.0 からの reverse-derived。ワークスペース新設に伴う逆起票）
