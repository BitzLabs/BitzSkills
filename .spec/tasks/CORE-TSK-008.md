---
implements: CORE-NFR-001
depends_on: [CORE-TSK-007]
boundary: scripts/release_check.py, tests/
status: done
---

### 委譲レジストリ整合の機械検証（release_check.py ＋ テスト先行）

- **作業内容**: DSN-001 §6 の4検査（agent 実在・ティア順序整合・モデル名の外部直書き禁止・違反時
  非ゼロ終了）を release_check.py に追加。tests/ にテスト先行で正常系＋各違反系フィクスチャを実装。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
