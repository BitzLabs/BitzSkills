---
implements: SDD-FR-129
depends_on: [SDD-TSK-011]
boundary: plugins/bitz-sdd/skills/sdd-docs/scripts/migrate_docs.py, tests/test_migrate_docs.py
status: pending
---

### 旧8章の安全な移行CLI

- **作業内容**: dry-run既定、全件preflight、hash付きmanifest、apply / rollbackを持つ移行CLIと、
  原子停止・冪等性を含む回帰テストを追加する。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
