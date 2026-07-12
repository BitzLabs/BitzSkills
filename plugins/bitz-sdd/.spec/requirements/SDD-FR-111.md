---
id: SDD-FR-111
version: 1.0
status: draft
domain: reporting
priority: medium
origin: skills/sdd-report/SKILL.md v0.2.2（reverse-derived）
verification_method: manual-check
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-111 統合レポートにおける集計対象ステータスと構成

- **説明**: 自動生成される統合進捗レポートは、要件ライフサイクル、レビュー判定結果、タスク進行状況などの主要メトリクスを正しく反映しなければならない。本要件は公開契約に該当する。
- **受入基準 (EARS)**:
  - WHEN `sdd_report.py` がレポートを生成する THEN システムは、要件ライフサイクル別（`draft`, `approved`, `implementing`, `verified`, `promoted`）のカウント、レビュー判定結果（`PASS`, `CONDITIONAL_PASS`, `FAIL`）、およびタスク進捗（`todo`, `doing`, `done`）を自動集計してレポートに含める SHALL
- **検証手段**: SKILL.md / references の目視確認 + skill-validator チェックリスト
- **Revision History**:
  - 1.0 (2026-07-12) 初版（実装 v1.4.5 からの reverse-derived。ワークスペース新設に伴う逆起票）
