---
implements: FLW-NFR-014
depends_on: [FLW-TSK-122]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_platform.py,plugins/bitz-flow/skills/flow-core/scripts/flowlib/cli.py,tests/test_flow_m2_closed_result_contract.py,tests/test_flow_m2_platform_probe.py,plugins/bitz-flow/.spec/design/FLW-DSN-017.md,plugins/bitz-flow/.claude-plugin/plugin.json,plugins/bitz-flow/plugin.json,plugins/bitz-flow/.codex-plugin/plugin.json
status: implementing
---

### 保証scopeをLinuxへ限定し公開経路の未捕捉例外を塞ぐ

`FLW-REV-028:GP-005`（P0）および`GP-003`。裁定参照:
`.spec/reports/decision-2026-08-24-linux-only-scope.md`。

- **実測した欠陥**:
  - `collision_key`は`case_semantics == "insensitive"`のとき`folded_component`を必須と
    するが、probeに導出経路が無く`plan()`も渡さない。再現すると`ContractError`が送出される。
  - `ContractError`は`ValueError`派生であり、CLIが捕捉する3型
    （`WorktreeChildTimeoutError`／`WorktreeUnsupportedPlatformError`／
    `WorktreeRuntimeError`）のいずれでもない。**closed resultではなくtracebackになる。**
  - これは特定1経路の問題ではなく**公開result契約の穴**である。想定外例外が
    公開経路へ出ないことを保証する仕組みが無い。
- **作業内容**:
  - **公開経路の網**: dispatcher単位で想定外例外を closed result（`UNAVAILABLE` /
    `result-indeterminate`）へ写す。例外型を列挙する方式ではなく、
    handlerの外側で受け止める。内部の型名・traceback・path断片を公開resultへ漏らさない。
  - **保証scope**: `worktree_platform`へ保証対象platformを明示し、対象外は
    理由付きで`UNSUPPORTED_FILESYSTEM`へ閉じる。macOS／Windowsのprobe実装は残す。
  - **case-insensitive**: 案B（裁定済み）に従い`UNSUPPORTED_FILESYSTEM`へ閉じる。
    folding規則を新設しない。理由を`reasons`へ載せ、`collision_key`へ到達させない。
  - `FLW-DSN-017` §1.1／§3.2／§13.5 の保証範囲をLinuxへ限定する。
- **完了条件**:
  - **公開経路（`flow.py`別process起動）で、いかなる入力でもtracebackを出さないこと**
    （production black-box test）。
  - `plan()`がcase-insensitive環境で例外ではなく closed result へ閉じること。
  - 対象外platformが理由付きで不支持になること。
  - §1.1／§13.5 の保証範囲がLinuxのみになっていること。
- **見積り**: 実装PR 1本・1 session。
- **実行判定**: `GP-005`はP0であり他の是正の検証を妨げるため最優先で行う。
  macOS／Windowsのprobe実装は削除しない（再開条件は裁定記録を参照）。
