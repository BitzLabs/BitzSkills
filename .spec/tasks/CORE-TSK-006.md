---
implements: CORE-FR-005
depends_on: []
boundary: plugins/bitz-sdd/skills/sdd-core/scripts/spec_update.py, tests/test_spec_update.py
status: done
---

### spec_update.py の実装（テスト先行）

- **作業内容**: `spec_update.py` を stdlib のみで実装する。sdd-core の権限マトリクス
  （lifecycle.md）をコードで強制し、人間専用遷移（draft→approved / open→accepted /
  verified→promoted / 任意→deprecated）は `--by-human` なしで拒否、エージェント許容遷移は無フラグで適用、
  未定義遷移は誰でも拒否する。遷移時に frontmatter status を更新し STATE.md へ記録追記。
  テストは先に作成した `tests/test_spec_update.py`（人間専用遷移の拒否・許可、エージェント遷移、
  不正遷移拒否、STATE.md 追記）。
- **実施記録**: 2026-07-13 実施。テスト先行 → 実装 → 全 green。SKILL.md・lifecycle.md へ参照追記。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
