---
implements: FLW-FR-001
depends_on: [FLW-TSK-001, FLW-TSK-002]
boundary: plugins/bitz-flow/.spec/, plugins/bitz-flow/**/plugin.json, .claude-plugin/marketplace.json, plugins/bitz-flow/README.md, tests/test_worktree_ops.py
status: done
---

### 統合検証とリリース整合

- **作業内容**: 要件由来のテスト仕様と検証記録を整備し、skill / plugin の version を規約どおり更新する。全体検査後に要件・spec-issue を完了状態へ遷移する。
- **完了条件**: pytest、skill-validator、spec inspect、release_check がすべて実出力で成功し、要件からテスト・実装まで追跡できる。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
