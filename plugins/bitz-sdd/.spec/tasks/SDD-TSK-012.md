---
implements: SDD-FR-126, SDD-FR-127, SDD-FR-128
depends_on: [SDD-TSK-011]
boundary: plugins/bitz-sdd/skills/sdd-docs/scripts/sdd_sync.py, tests/test_sdd_sync.py
status: done
---

### 日本語章への双方向同期マッピング

- **作業内容**: 既存のDiscovery・設計・データ・ドメインストーリー同期先を日本語章へ変更し、
  pull / push / diffとmtime保護の回帰テストを更新する。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
