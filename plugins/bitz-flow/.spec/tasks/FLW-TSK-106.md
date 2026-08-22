---
implements: FLW-NFR-014
depends_on: []
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_contract.py,plugins/bitz-flow/skills/flow-core/schemas/worktree-v2/contract-bundle-v2.schema.json,tests/test_flow_m2_contract_kernel.py
status: implementing
---

### pure contractと単一bundle schemaを固定する

- **作業内容**: canonical JSON、native path、platform identity、digest、uint64、strict SemVer、
  operation event、receipt、contract bundleのclosed schema/codecを副作用なしで実装する。
  - schema別activation manifestを作らず、全memberを列挙する単一bundle manifestを正とする。
  - bundle member欠落、重複schema ID、未知field、codec round-trip不一致を拒否する。
  - OS、Git、subprocess、鍵registry、archive backendへ依存しない。
- **完了条件**: schemaとcodecの双方向一致、NFC/NFD非衝突、2^53・2^64境界、非canonical値、
  bundleの部分集合をfail-closedに拒否し、pure testが外部processを起動しない。
- **見積り**: FLW-TSK-107と実装PR 1へまとめ、2 sessionを上限とする。
- **実行判定**: 公開契約の最下層。改訂設計の再Design Gateまで実装を再開しない。
