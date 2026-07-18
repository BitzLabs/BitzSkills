---
implements: CORE-FR-004
depends_on: []
boundary: plugins/bitz-sdd/skills/sdd-core/scripts/spec_scaffold.py, tests/test_spec_scaffold.py
status: done
---

### spec_scaffold.py の next_number() 採番衝突を修正（SI-SDD-006）

- **作業内容**: `next_number()` の正規表現をサフィックス付きファイル名（`DSN-001-delegation-registry.md`
  等）にもマッチするよう `^{prefix}-(\d+)(-.*)?\.md$` に緩める。design 種別の起票で既存の
  サフィックス付き DSN ファイルが走査から漏れず、ID が重複しないことを確認する回帰テストを
  `tests/test_spec_scaffold.py` に追加する（`test_design_number_skips_suffixed_existing_file`）。
  既存の全テストが green のままであることを確認する。
- **実施記録**: 2026-07-18 実施。pytest 全green・release_check/spec_inspect PASS。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
