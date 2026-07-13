---
implements: CORE-FR-004
depends_on: []
boundary: plugins/bitz-sdd/skills/sdd-core/scripts/spec_scaffold.py, tests/test_spec_scaffold.py
status: done
---

### spec_scaffold.py の実装（テスト先行）

- **作業内容**: `spec_scaffold.py` を stdlib のみで実装する。プレフィックスの既存最大番号+1 を採番し、
  requirement / spec-issue / task の frontmatter 付き雛形（spec_inspect PASS 書式）を生成する。
  既存ファイルは上書きせず失敗。副作用は `.spec/` 配下への新規生成のみ。テストは先に作成した
  `tests/test_spec_scaffold.py`（採番一意性・001 起番・プレフィックス分離・書式互換・非上書き・副作用限定）。
- **実施記録**: 2026-07-13 実施。テスト先行 → 実装 → 全 green。SKILL.md「起票・status 遷移」節と
  lifecycle.md 採番規則へ参照追記。bitz-sdd を bump。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
