---
implements: [QLT-FR-007]
depends_on: [QLT-TSK-002]
boundary: plugins/bitz-quality/skills/quality-design/, tests/test_quality_design.py
status: done
---

### quality-design 観点・ケース・データ設計サブエージェント

- **作業内容**: テスト観点一覧（機能/異常系/境界値/セキュリティ/互換性）の自動導出スクリプト、具象テストケース生成スクリプト、および境界値テストデータ生成スクリプトを実装する。
- **完了条件**:
  - `plugins/bitz-quality/skills/quality-design/scripts/quality_viewpoints.py` の実装
  - `plugins/bitz-quality/skills/quality-design/scripts/quality_cases.py` の実装
  - テスト観点・テストケース・テストデータ生成のユニットテストが PASS すること。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない。
