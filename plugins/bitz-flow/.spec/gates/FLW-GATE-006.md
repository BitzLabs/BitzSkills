---
id: FLW-GATE-006
gate: design
date: 2026-08-24
arbiter: hide
scope: [FLW-CON-008, FLW-DSN-017]
confirmed_decision_refs:
  - .spec/reports/decision-2026-08-24-flw-con-008-approval.md
checklist_ref: skills/sdd-core/references/gates.md#2-design-gateproposed--active
---

# FLW-GATE-006 design Gate 通過記録

- **裁定者**: hide
- **対象**: 上記 `scope` の 2 件
- **確認した裁定記録**: 上記 `confirmed_decision_refs`
- **チェックリスト**: `skills/sdd-core/references/gates.md#2-design-gateproposed--active`
- **備考**: 2026-08-24にユーザーが「承認します。設計を進めましょう」と裁定した。
  `FLW-CON-008`を`approved`へ、`FLW-DSN-017` v2.3を`active`へ遷移する。

## FLW-CON-008 7観点の記録

本Gateは`FLW-CON-008`に拘束される初のdesign Gateである。同要件により、7観点それぞれへ
`実証済み` / `未実装境界` / `検証計画` のいずれかを記録する。

| # | 観点 | 判定 | 根拠 |
|---:|---|---|---|
| 1 | 接続完全性 | **未実装境界** | `FLW-DSN-017` §13.1 行6〜11。worktree全8 handlerが`_GATED_HANDLERS`にあり公開dispatcher非到達。`PF.evaluate_platform()`のproduction呼出元が無く`plan()`は`platform evidence is required`で必ず例外停止する |
| 2 | 失敗原子性 | **検証計画** | §13.3 #2はv2.3の単一durable record統合で構造的に解消。#6のmarker適格性再検証は`SI-FLW-089`で実装予定 |
| 3 | 有限収束性 | **未実装境界** | §13.4。`worktree_runtime.py`の全subprocess（L66/L140/L325/L732）に`timeout=`が無い。`process.py`の監督機構は実装済みだが未使用 |
| 4 | platform実在性 | **未実装境界** | §13.5。linux/macos/windowsとも実観測未実施。`native_component_from_posix`をOS非依存に使用している |
| 5 | 証跡妥当性 | **未実装境界** | 現行の`verified`証跡はfixture注入経路に基づく。`SI-FLW-090`で是正 |
| 6 | legacy排除 | **未実装境界** | §13.6の5件がproductionコードに残存。negative testも未実装 |
| 7 | 状態意味保存 | **検証計画** | §13.2の不変条件を`SI-FLW-088`／`089`で実装予定 |

**`実証済み` は0件である。** したがって`FLW-CON-008`の受入基準に従い、本Gateは
接続の成立をPASS根拠にしない。

## 本Gateが承認する範囲

承認するのは**是正の設計方針としての妥当性**に限る。

1. §13の6表が実測に基づき、未接続を未接続として記載していること。
2. §4.2の単一durable record統合が、2回publish間のcrash空隙（Git副作用0件かつ
   nonce消費済みかつ`INDETERMINATE`）を構造的に解消すること。
3. `SI-FLW-084`〜`090`が7観点すべてに追跡先を持つこと。

`FLW-REV-027`のGate blocking条件（production既定dispatcher実走、3platform実観測、
全crash境界、finite timeout）は**本Gateでは解除されない**。worktree operationの公開集合は
gatedを維持する。解除は是正実装後、同じ5観点の再レビューでPASSを得たときに限る。

## 次工程

`.spec/reports/decision-2026-08-24-flw-rev-027-remediation.md`が固定した依存順で実装タスクへ分解する。
`SI-FLW-087`の永続形式変更は本Gateで承認した`FLW-DSN-017` §4.2に含まれるため、追加のDesign Gateを要しない。
