---
implements: SDD-FR-001
depends_on: []
boundary: plugins/bitz-sdd/skills/sdd-core/scripts/spec_inspect.py, tests/test_spec_inspect.py
status: done
---

### spec_inspect のタスク ID 既知化と回帰テスト（reverse-derived の完了タスク）

- **作業内容**: inspect の幽霊判定で `.spec/tasks/` のファイル名 stem を既知 ID として
  除外。tests/test_spec_inspect.py にタスク間 depends_on / specs 文書からの言及 /
  存在しないタスク ID の検出継続の回帰ケースを追加。
- **実施記録**: 2026-07-11 頃実施済み（PR #22 に同乗）。本タスクはワークスペース新設
  （2026-07-12）に伴い、実装済み修正へ要件を紐づける逆起票の記録であり、新規の実装作業はない。
- **備考**: 由来はルート SI-CORE-003（2026-07-11 人間裁定で accepted）。
  タスク ID はファイル名が正（本文に自身の ID は書かない）。
