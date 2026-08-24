# 裁定記録 — FLW-CON-008の承認とFLW-DSN-017 v2.3のDesign Gate

- **日付**: 2026-08-24
- **裁定者**: hide（リポジトリ所有者）
- **対象**: `FLW-CON-008`、`FLW-DSN-017` v2.3
- **裁定原文**: 「承認します。設計を進めましょう」
- **提示済み提案**: `FLW-CON-008`（設計完了判定の実証義務）と、それを`implements`する
  `FLW-DSN-017` v2.3（§13の6表・§4.2の単一durable record統合）の解説を提示し、
  両者が`draft`であること・承認とactive化が人間裁定であることを明示したうえで裁定を求めた。
- **記録者**: claude（裁定者の明示指示に基づく代行記録・実行者未検証）

## 裁定

1. `FLW-CON-008`を`approved`とする。7観点と6設計成果物をbitz-flowの設計完了判定の
   規範とし、`tests/test_flow_design_completion_contract.py`による機械検証を発効させる。
   適用は本要件の発効日（2026-08-24）以降のdesign GatePassageに限り、
   `FLW-GATE-001`〜`005`へは遡及しない。
2. `FLW-DSN-017` v2.3をDesign Gate通過とし`active`化する。GatePassageは`FLW-GATE-006`。

## このDesign Gateが承認する範囲（限定）

**本Gateは接続の成立を承認しない。** `FLW-DSN-017` §13.7が記録するとおり、7観点に
`実証済み`は0件であり、内訳は未実装境界5件・検証計画2件である。本Gateが承認するのは
**是正の設計方針としての妥当性**、すなわち次の3点に限る。

- §13の6表が、実測に基づき未接続を未接続として記載していること。
- §4.2の単一durable record統合が、2回publish間のcrash空隙（Git副作用0件かつnonce消費済みかつ
  `INDETERMINATE`）を構造的に解消すること。
- `SI-FLW-084`〜`090`が7観点すべてに追跡先を持つこと。

`FLW-REV-027`のGate blocking条件（production既定dispatcher実走、3platform実観測、
全crash境界、finite timeout）は本Gateでは解除されない。worktree operationの公開集合は
gatedを維持し、解除は是正実装後の再レビューPASSによってのみ行う。

## 実装着手条件

- `FLW-CON-008`を`approved`へ、`FLW-DSN-017`を`active`へ遷移し、本記録を`decision_ref`として残す。
- `FLW-GATE-006`へ7観点の現状（`実証済み`0件）を記録する。記録内容は
  `tests/test_flow_design_completion_contract.py::test_design_gate_records_all_seven_criteria`が検査する。
- 実装は`.spec/reports/decision-2026-08-24-flw-rev-027-remediation.md`が固定した依存順に従う:
  `SI-FLW-085`→`SI-FLW-084`→`SI-FLW-086`／`SI-FLW-087`→`SI-FLW-088`→`SI-FLW-089`→`SI-FLW-090`。
  `SI-FLW-091`は独立に着手できる。
- `SI-FLW-087`は永続形式変更を伴うが、その設計は本Gateで承認済みの`FLW-DSN-017` §4.2に含まれる。
  したがって追加のDesign Gateを要しない。
