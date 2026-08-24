# 裁定記録 — FLW-NFR-014をverifiedからimplementingへ戻す

- **日付**: 2026-08-24
- **裁定者**: hide（リポジトリ所有者）
- **対象**: `FLW-NFR-014`
- **裁定原文**: 「FLW-NFR-014のimplementing 許可します」
- **提示済み提案**: `FLW-TSK-116`／`FLW-TSK-117`を起票した結果、`spec_inspect`が
  `[trace] FLW-NFR-014: verified/promotedだが未完了local taskがある`を検出した。
  同要件は2026-08-23にfixture注入経路の証跡で`verified`へ遷移したが、production接続は
  未完了であり、残作業を正直にタスク化したことで既存の過大主張が機械検出された。
- **記録者**: claude（裁定者の明示指示に基づく代行記録・実行者未検証）

## 裁定

`FLW-NFR-014`を`verified`→`implementing`へ戻す。`verified`の取り消しは機械が代行できない
遷移であり（`spec_update.py`の`("verified", "implementing"): "human"`）、人間裁定を要する。

## 根拠

`FLW-REV-027`（FAIL 2.12）は、同要件の`verified`証跡がproduction経路を覆っていないと判定した。
`FLW-DSN-017` §13.1が実測で示すとおり、当時は次の状態だった。

- worktree全8 handlerが公開dispatcher非到達。
- `PF.evaluate_platform()`のproduction呼出元が存在せず、`plan()`は必ず例外停止した。
- worktree経路の全subprocessに`timeout=`が無かった。

これらは`FLW-TSK-115`〜`117`で順次解消しているが、`SI-FLW-087`〜`090`が未了であり、
7観点に`実証済み`は0件である。したがって`verified`の主張は実態に先行している。

## 適用範囲

本裁定は`FLW-NFR-014`のstatusだけを対象とする。次は変更しない。

- `FLW-DSN-017`は`active`のまま（`FLW-GATE-006`で通過済み）。
- 完了済みtask（`FLW-TSK-106`〜`114`）の`done`は取り消さない。個々のtaskは宣言した
  変更境界の作業を完了しており、過大主張は要件レベルの`verified`にある。
  task境界の再記録は`SI-FLW-090`の管轄とする。
- worktree operationの公開集合はgatedのまま維持する。

## 再verifiedの条件

`SI-FLW-084`〜`090`が実証を伴って解消し、`FLW-REV-027`と同じ5観点の再レビューで**PASS**を
得たうえで、`FLW-CON-008`の7観点に`実証済み`が揃うこと。fixture注入経路の証跡を
再verifiedの根拠にしない。
