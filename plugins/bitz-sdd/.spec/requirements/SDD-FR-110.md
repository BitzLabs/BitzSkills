---
id: SDD-FR-110
version: 1.0
status: approved
domain: reporting
priority: high
origin: skills/sdd-report/SKILL.md v0.2.2（reverse-derived）
verification_method: manual-check
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-110 開発進捗・品質レポートの自動生成と出力

- **説明**: BitzSDD ワークフローの進捗や品質を可視化するため、`sdd_report.py` は仕様・検証マスターから情報を自動走査し、人間向けのレポートを出力しなければならない。本要件は公開契約に該当する。
- **受入基準 (EARS)**:
  - WHEN プロジェクトルートを引数に指定して `sdd_report.py` を実行する THEN システムは `.spec/` ディレクトリ配下の状態を走査して自動集計を行い、その結果を `.spec/reports/status-report.md` にマークダウン形式で出力する SHALL
- **検証手段**: SKILL.md / references の目視確認 + skill-validator チェックリスト
- **Revision History**:
  - 1.0 (2026-07-12) 初版（実装 v1.4.5 からの reverse-derived。ワークスペース新設に伴う逆起票）
  - 1.0 (2026-07-12) 人間裁定により approved 化（チャット指示）
