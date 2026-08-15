---
implements: [QLT-FR-015]
depends_on: []
boundary: plugins/bitz-quality/skills/quality-core/scripts/quality_status.py, tests/test_quality_status.py
status: done
---

### エージェント向け軽量QA状態照会スクリプト quality_status.py の実装

- **作業内容**: `quality_status.py` を実装し、エージェントが 1 手で現在の QA フェーズ（intake/scoring/design/gate/trace/done）、ゲート合否、未解決指摘、EARS要件充足率を把握し、次に実行すべき推奨アクションを提示する。
- **完了条件**:
  - `plugins/bitz-quality/skills/quality-core/scripts/quality_status.py` の実装
  - `tests/test_quality_status.py` の実装と全テスト PASS
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない。
