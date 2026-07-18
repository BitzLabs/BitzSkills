---
implements: FLW-FR-001
depends_on: []
boundary: plugins/bitz-flow/skills/flow-pr/scripts/branch_preflight.py, plugins/bitz-flow/skills/flow-pr/SKILL.md, tests/test_branch_preflight.py
status: done
---

### branch preflight の実装

- **作業内容**: merged PR・差分・open PR の base/mergeability を読み取り専用で検査する CLI を追加し、判定・timeout・許可リスト JSON の単体テストを先行実装する。flow-pr の契約と復旧手順も更新する。
- **完了条件**: READY / INDETERMINATE / REUSE_BLOCKED の終了コードと、秘密情報を含まない診断がテストで固定されている。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
