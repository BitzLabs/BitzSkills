---
implements: SDD-FR-150
depends_on: [SDD-TSK-039]
boundary: scripts/release_check.py, skills/sdd-docs/SKILL.md, skills/sdd-discovery/SKILL.md, tests/test_release_check.py
status: done
---

### 同期マッピングの二重定義を機械検証で防ぐ

- **作業内容**: `release_check.py` に `check_sync_mapping` を追加し、`sdd_sync.py` の
  `DEFAULT_MAPPING` を正として sdd-docs / sdd-discovery の SKILL.md に置いた
  `sync-mapping` マーカーおよび人間可読の同期表と三者照合する。sdd-discovery は
  `.spec/discovery/` 部分集合とだけ照合する。併せてマッピングの 1:1 性も検査する。
  検証様式は SDD-FR-140（フェーズ正規語彙）の前例に揃える。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
