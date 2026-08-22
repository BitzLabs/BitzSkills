---
implements: FLW-NFR-014
depends_on: [FLW-TSK-106]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_lease.py,plugins/bitz-flow/skills/flow-core/schemas/worktree-v2/target-lease-v2.schema.json,plugins/bitz-flow/skills/flow-core/schemas/worktree-v2/fencing-counter-v2.schema.json,plugins/bitz-flow/skills/flow-core/schemas/worktree-v2/mutation-intention-v2.schema.json,plugins/bitz-flow/skills/flow-core/schemas/worktree-v2/mutation-postcondition-v2.schema.json,plugins/bitz-flow/skills/flow-core/schemas/worktree-v2/lock-namespace-v2.schema.json,plugins/bitz-flow/skills/flow-core/schemas/worktree-v2/activation/lease-records-v2.json,tests/test_flow_m2_process_lease.py
status: pending
---

### process間lease・fencing状態機械・MutationGuardianを実装する

- **作業内容**: common-dirの保護済みnamespaceにprocess間OS lock、`lock-namespace.json`、単調増加
  uint64 fencing token、durable state machineを実装する。
  - `LOCKED → TOKEN_DURABLE → INTENTION_DURABLE → MUTATING → POSTCONDITION_DURABLE → DONE /
    QUARANTINED`の順序とfile/directory durabilityを守る。
  - lock namespace identity不一致、counter欠損・巻戻り・overflow、receipt下限未満を
    `INDETERMINATE`としてquarantineする。
  - `MutationGuardian`がLinux/macOSではlease FDとprocess group、Windowsではlease handleと
    Job Objectを保持し、Git child終了statusをdurableに確定する。
  - regular fileとdirectory identityを別schemaで扱い、fencing tokenをuint64 decimal stringとして
    全recordへ統一する。担当schema/codec/round-tripを揃えてowner activation manifestをactive化する。
- **完了条件**: 複数process競合でmutationへ進むprocessが最大1つとなり、各crash pointからの再開が
  設計表どおり収束する。child終了を証明できない場合は後続mutationを停止し、2^53境界・2^64-1・overflowの
  cross-language vectorとlease recordのschema/codec双方向一致を確認する。
- **実行判定**: 並行性・crash safetyを扱う難実装。外部相談先が利用不能なため自己実行するが、
  OS capabilityが設計matrixを満たさない場合は`UNSUPPORTED`を維持してscope裁定へ戻す。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
