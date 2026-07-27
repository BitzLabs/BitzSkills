---
implements: SDD-FR-143
depends_on: []
boundary: skills/sdd-core/scripts/spec_transaction.py, tests/test_spec_transaction.py
status: done
---

### workspace transaction基盤を実装する

- **作業内容**: atomic no-replace lock、SHA-256 payload、PREPARED/APPLIED/COMMITTED journal、
  durable replace、recoveryを`spec_transaction.py`へ実装し、障害境界をunit-testする。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
