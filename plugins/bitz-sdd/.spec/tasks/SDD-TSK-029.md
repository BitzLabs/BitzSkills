---
implements: SDD-FR-143
depends_on: [SDD-TSK-028]
boundary: skills/sdd-core/scripts/spec_trace.py, spec_update.py, spec_inspect.py, tests/test_spec_update.py, tests/test_spec_inspect.py
status: done
---

### updateの認可・task前提・監査eventを実装する

- **作業内容**: 共有task索引、local task前提、`--interactive-decision`、構造化STATE event、
  transaction recovery CLI、inspectの迂回検出を実装する。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
