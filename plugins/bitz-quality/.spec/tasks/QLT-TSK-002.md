---
implements: [QLT-FR-006]
depends_on: []
boundary: plugins/bitz-quality/skills/quality-design/, tests/test_quality_design.py
status: done
---

### quality-design 影響分析・不具合傾向分析サブエージェント

- **作業内容**: `quality-design` スキルを新規作成し、コード差分・依存関係から影響範囲（直接/間接/DB）を抽出するスクリプトおよび、過去の類似バグや再発防止ルールからリスク要因を特定する不具合傾向分析スクリプトを実装する。
- **完了条件**:
  - `plugins/bitz-quality/skills/quality-design/SKILL.md` の作成（frontmatter・分業手順）
  - `plugins/bitz-quality/skills/quality-design/scripts/quality_impact_analysis.py` の実装
  - `plugins/bitz-quality/skills/quality-design/scripts/quality_bug_analysis.py` の実装
  - 影響分析および不具合分析のユニットテストが PASS すること。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない。
