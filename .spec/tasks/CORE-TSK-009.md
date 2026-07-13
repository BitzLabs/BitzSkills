---
implements: [CORE-FR-006, CORE-FR-007, CORE-FR-008, CORE-CON-007]
depends_on: []
boundary: plugins/bitz-sdd/skills/sdd-implement/
status: done
---

### 委譲アルゴリズム＋委譲ゲート（delegation-routing.md ＋ SKILL.md）

- **作業内容**: DSN-001 §4 の相対選択アルゴリズム（役割分類→下位委託→上位相談→損益分岐）を
  新規 `references/delegation-routing.md` に実装。SKILL.md にタスク着手前の委譲ゲート手順を追加し、
  delegation-routing.md を参照させる。モデル名は直書きせず役割で参照する。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
