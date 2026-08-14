---
implements: [QLT-FR-016]
depends_on: [QLT-TSK-009]
boundary: plugins/bitz-quality/skills/quality-report/, tests/test_quality_report.py
status: done
---

### 人間向け総合品質報告書 quality-report スキルの実装

- **作業内容**: `quality-report` スキル（SKILL.md, `quality_report.py`）を実装し、総合スコア・リスクレベル・3層ゲート合否・指摘一覧・SDD要件トレーサビリティ・再発防止ルール蓄積状況を統合した Markdown 報告書（`.spec/quality/reports/quality-summary-report.md`）を出力する。
- **完了条件**:
  - `plugins/bitz-quality/skills/quality-report/SKILL.md` の作成
  - `plugins/bitz-quality/skills/quality-report/scripts/quality_report.py` の実装
  - `tests/test_quality_report.py` の実装と全テスト PASS
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない。
