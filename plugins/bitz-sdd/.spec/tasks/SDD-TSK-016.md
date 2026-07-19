---
implements: SDD-FR-131
depends_on: []
boundary: plugins/bitz-sdd/skills/sdd-core/scripts/spec_update.py, plugins/bitz-sdd/skills/sdd-core/references/lifecycle.md, tests/test_spec_update.py, bitz-sdd 3マニフェスト
status: done
---

### spec-issue の accepted→rejected 遷移追加（タスク ID はファイル名が正）

- **作業内容**: テスト先行で tests/test_spec_update.py に accepted→rejected の許可/拒否/回帰
  テストを追加（red 確認）→ spec_update.py の TRANSITIONS["spec-issue"] に
  `("accepted", "rejected"): "human"` を追加（green 確認）→ lifecycle.md の遷移図・補足に
  再裁定分岐と `- **再裁定**:` 語彙を追記 → bitz-sdd マニフェスト minor bump。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
