---
implements: CORE-CON-010
depends_on: []
boundary: AGENTS.md, .spec/spec-issues/SI-CORE-029.md
status: done
---

### version bump のコミット位置規約を実運用へ整合

- **作業内容**: AGENTS.md の version bump 規約を、同一 PR への包含を必須としつつ
  コミット位置は固定しない表現へ変更する。実装コミットへの同梱を推奨し、bump 単独コミットも
  許容することで、テスト先行フローのコミット順序と規約を整合させる。
- **実施記録**: 2026-07-18 実施。release_check PASS、pytest 167件 green、
  spec inspect 全7ワークスペース PASS。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
