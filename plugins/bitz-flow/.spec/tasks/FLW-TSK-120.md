---
implements: FLW-NFR-014
depends_on: [FLW-TSK-119]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_recovery.py,plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_promotion.py,tests/test_flow_m2_marker_eligibility.py,tests/test_flow_m2_recovery.py,plugins/bitz-flow/.spec/design/FLW-DSN-017.md,plugins/bitz-flow/.claude-plugin/plugin.json,plugins/bitz-flow/plugin.json,plugins/bitz-flow/.codex-plugin/plugin.json
status: implementing
---

### reconcile closure前にactive markerの適格性を確定する

`SI-FLW-089`（`FLW-REV-027:SYN-006` P1）。

- **実測した欠陥**: `worktree_recovery.reconcile()`は
  (1) target lock取得 → (2) 再authorize・再audit → (3) **closure追記（不可逆）** →
  (4) target lock解放 → (5) promotion lockでmarker解放、の順で進む。
  marker適格性を検査するのは`release_reconciled_operation`（手順5）であり、
  marker欠落・不正・不一致は**closureを追記した後**に判明する。
  不可逆な追記が適格性確認より先行している。
- **作業内容**:
  - `worktree_promotion.inspect_active_marker()`（read-only・promotion lock下）を追加する。
  - `RecoveryAudit`へmarker存在・operation ID・bundle digestを束縛する（plan時）。
  - `reconcile()`のclosure追記**前**にpromotion lock下で再検証する。marker欠落・
    不一致ならclosureを1件も追記せずに閉じる。
  - **target lockとpromotion lockを同時保持しない**不変条件を保護する
    （検査 → promotion lock解放 → target lock → closure → promotion lock → marker解放）。
  - 正常`DONE`（markerが既に解放済み）や既にclosedのoperationへreconcileを案内しない。
- **完了条件**:
  - marker欠落・不一致で**closure 0件**であること。
  - closure後・marker closure前のcrashが、同一decisionの再試行で**単一closure**へ
    収束すること（冪等）。
  - target lockとpromotion lockを同時保持しないこと（機械検査）。
- **見積り**: 実装PR 1本・1 session。
- **実行判定**: `FLW-TSK-119`の後。lock order不変条件を壊さないこと。
