---
implements: SDD-FR-144
depends_on: [SDD-TSK-028]
boundary: skills/sdd-core/scripts/spec_scaffold.py, tests/test_spec_scaffold.py
status: done
---

### scaffoldを排他的かつ回復可能にする

- **作業内容**: lock取得後の再採番、WAL、atomic no-replace公開、競合時の安全側停止と
  3分類recoveryを`spec_scaffold.py`へ適用する。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
