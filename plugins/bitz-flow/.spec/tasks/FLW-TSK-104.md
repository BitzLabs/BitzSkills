---
implements: FLW-NFR-012
depends_on: []
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_runtime.py,tests/test_flow_m2_runtime.py,plugins/bitz-flow/.spec/tasks/FLW-TSK-104.md
status: implementing
---

### M2 runtime の apply に target guard を結線する

- **作業内容**: 承認検証後、nonce 消費と最初の副作用の前に、worktree directory・registry・local ref・index の canonical target を一括取得する。guard は PENDING receipt、各 mutation、DONE/QUARANTINED receipt まで保持し、各副作用の直前に所有者と fencing token を再照合してから実行する。
- **完了条件**: 同じ worktree target に対する別 operation が、先行 operation の副作用直前で `BLOCKED` となり、副作用を起こさない。先行 operation 完了後は guard が解放される。
- **備考**: process 間 coordinator と crash 後の永続 quarantine は後続タスクで扱う。本タスクは runtime に既存 target guard を実際に適用する結線に限定する。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
