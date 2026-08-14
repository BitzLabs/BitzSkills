---
implements: [QLT-FR-013, QLT-FR-014]
depends_on: []
boundary: plugins/bitz-quality/skills/quality-measurand/, tests/test_quality_measurand.py
status: done
---

### quality-measurand スキルおよびメトリクス・ミューテーション自己診断の実装

- **作業内容**: `quality-measurand` スキルを新規作成し、統合品質メトリクス測定スクリプト（要件充足率・ゲート通過率・ルール蓄積数・総合健全性スコア）およびミューテーション自己診断スクリプト（人工欠陥注入とKill判定）を実装する。
- **完了条件**:
  - `plugins/bitz-quality/skills/quality-measurand/SKILL.md` の作成
  - `plugins/bitz-quality/skills/quality-measurand/scripts/quality_measurand.py` の実装
  - `tests/test_quality_measurand.py` の実装と全件 PASS
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない。
