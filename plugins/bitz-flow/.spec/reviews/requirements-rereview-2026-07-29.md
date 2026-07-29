---
id: FLW-REV-004
title: "bitz-flow v2 draft要件 多観点再レビュー"
status: active
version: 1.0
updated: 2026-07-29
owner: hide
decision: PASS
---

# FLW-REV-004 bitz-flow v2 draft要件 多観点再レビュー

## 結論

**PASS**。FLW-NFR-003から順に行った責務分割、トレース修正、後継発効規則、timebox、
Forward Recovery補強後のv2 draft要件は、要件承認ゲートへ提示できる。

- 集計スコア: **4.84**
- P0 critical: 0
- P1 major: 0
- P2 residual: 1
- spec inspect: 問題0、幽霊参照0、孤児要件0

## 対象

- `plugins/bitz-flow/.spec/discovery/*.md`
- `plugins/bitz-flow/.spec/design/*.md`
- `plugins/bitz-flow/.spec/requirements/*.md`
- `plugins/bitz-flow/.spec/reports/decision-2026-07-29-bitz-flow-v2-design-gate.md`
- `plugins/bitz-flow/.spec/STATE.md`

## 観点別判定

| 観点 | スコア | 判定 |
|---|---:|---|
| consistency | 5.00 | PASS |
| data-integrity | 4.65 | PASS |
| operations | 5.00 | PASS |
| risk | 4.70 | PASS |
| business | 5.00 | PASS |

## レビュー中に解消した問題

1. SI-FLW-002〜005のaccepted内容と設計・要件の誤対応を訂正した。
2. M1〜M5予算を初期budgetとし、実績と人間referenceによる再校正を追加した。
3. milestoneを複数PRから成る出荷・rollback境界として定義した。
4. 責務分割したFLW-NFR-003/004、FLW-CON-002のversionを更新した。
5. remote branch削除応答喪失後のexpected SHA残存を再plan・再承認へ固定した。
6. atomic replaceとdurability commit pointを分け、crash後の旧版/新版契約を実現可能化した。
7. FLW-FR-001の複合後継へFLW-FR-009を加えた。
8. M3 Issue/SDDとM4 PRの独立canaryを定義した。

## 残余リスク

cross-host GitHub createは分散lockではなく単一coordinator運用へ依存する。これは意図した
スコープ境界であり、安全を証明できない場合は`UNSUPPORTED`、重複検出時は`BLOCKED`として
自動close/deleteせず、M3/M4 Promotionを停止する。FLW-CON-004で検証するため承認ブロッカーではない。

## ゲート勧告

レビューPASSは人間による要件承認を代替しない。draft要件をapprovedへ進める前に、
本レビュー、FLW-REV-005、変更後diffを人間へ提示する。approved後もM0だけをtask分解し、
M0出口条件を満たすまでM1を開始しない。
