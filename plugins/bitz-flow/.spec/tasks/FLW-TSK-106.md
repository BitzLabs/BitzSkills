---
implements: FLW-NFR-014
depends_on: []
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_contract.py,plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_capability.py,plugins/bitz-flow/skills/flow-core/schemas/worktree-v2/approval-capability-v2.schema.json,plugins/bitz-flow/skills/flow-core/schemas/worktree-v2/file-identity-v2.schema.json,plugins/bitz-flow/skills/flow-core/schemas/worktree-v2/native-path-v2.schema.json,plugins/bitz-flow/skills/flow-core/schemas/worktree-v2/activation/approval-capability-v2.json,tests/test_flow_m2_contract_v2.py,tests/test_flow_m2_contract_kernel.py
status: implementing
---

### contract kernelとcapability v2の純粋契約を固定する

- **作業内容**: `FLW-DSN-017` §2・§5・§6の決定論的な契約処理だけを所有する。
  - canonical JSON、NFC受理境界、`sha256:<hex>`、uint64 decimal string、strict SemVerを
    OS・Git・process副作用なしでparse/encodeする。
  - native pathの可逆component表現、regular file/directory別のplatform identity、
    capability v2のclosed schema/codec/canonical vectorを固定する。
  - `approval_declaration_digest`をcapability署名payloadの必須fieldとし、v1、欠落、未知field、
    context不一致を既定値補完せず拒否する。
  - 自分が所有するschema、codec、activation manifest、round-trip testだけを同じ
    rollback単位で`active`にする。
  - filesystem観測、sentinel、entrypoint probe、OS lock、Git mutation、recoveryは本境界に入れない。
- **完了条件**: schemaとruntime codecのfield・round-tripが双方向一致し、NFD、未知field、
  platform/resource kind混在、NFC/NFD native path衝突、2^53・2^64境界、非canonical digest/SemVerの
  陽性対照がfail-closedになる。pure testがOS・Git・subprocessを起動しないことを検査する。
- **実行判定**: 公開契約の最下層。`FLW-DSN-017` v1.5の再レビューとDesign Gateまで
  実装を再開しない。Gate後は上位controllerとの逆依存を検出したら中断する。
- **既存証跡の扱い（2026-08-22）**: 再分割前の複合境界でschema契約`11 passed`、
  M2 runtime回帰`79 passed`、後続の対象suite`143 passed`を確認済み。これらは回帰証跡として
  保持するが、新しいcontract kernelの完了証拠とはみなさない。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
