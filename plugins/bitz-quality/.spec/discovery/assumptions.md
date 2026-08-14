---
id: QLT-DSC-007
title: "bitz-quality レビュー基盤 仮説検証ゲート"
status: draft
version: 1.0
updated: 2026-08-14
owner: br7.hide
---

# 仮説検証ゲート

## 仮説表

| ID | 分類 | 仮説 | 崩壊影響 | 状態 | テストと事前閾値 |
|---|---|---|---|---|---|
| H-Q1 | feasibility | 論理Reviewer契約を3platform adapterで等価に実行できる | クリティカル | 未検証 | 同一fixtureで必須field保持100%、verdict parity 100%。未達ならadapter設計をPivot |
| H-Q2 | feasibility | 個別結果とsynthesisを閉集合schemaで機械検査できる | クリティカル | 部分支持 | 欠落/未知/不正語彙/重複IDの陽性対照を100%検出。未達ならGate接続しない |
| H-Q3 | desirability | 専門観点分業が単一レビューより重大欠陥の検出を改善する | 高 | 未検証 | baseline比較を事前設計。改善なしなら必須観点数を縮小 |
| H-Q4 | viability | profile/adapter分離が観点追加時の変更波及を抑える | 高 | 未検証 | 追加観点fixtureでcore schema変更0。必要なら境界を再設計 |
| H-Q5 | feasibility | 現行`sdd-review`成果物を意味を失わず読取・再合成できる | クリティカル | 部分支持 | golden corpus全件で必須field100%、P0/P1消失0、verdict差0。未達なら移管No-Go |
| H-Q6 | safety | qualityをprovider化してもSDD/FlowのSSOTと副作用境界を侵害しない | クリティカル | 部分支持 | 権限外write 0、stale/unknownの誤PASS 0。違反時はadapterを無効化 |

## Discovery Gate提示

- **裁定**: Go（2026-08-14、人間。会話上の明示入力 `GO`）
- **Go条件**: H-Q1/Q2/Q5/Q6のテスト方法とkill閾値をDesign成果物へ引き継ぐこと。
- **No-Go条件**: `sdd-review`互換を保てない、またはqualityがSDD/FlowのSSOTを所有しないと成立しない場合。
- **未裁定事項**: 初期必須platform、profile上書き場所、モデルqualificationの母数・予算。
- **裁定者/裁定日**: br7.hide / 2026-08-14（ホスト上の本人性は未検証）
- **設計移行**: 許可
