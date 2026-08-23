---
id: FLW-CON-008
version: 1.1
status: draft
domain: governance
priority: high
origin: FLW-REV-027 / decision-2026-08-23-m2-post-implementation-retrospective.md §5-§6
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### FLW-CON-008 設計完了判定の実証義務（7観点と6設計成果物）

- **説明**: 設計成果物の横方向の整合ではなく、**利用者入口から最終状態までの縦方向の到達可能性**を
  Design Gate の通過条件にする。`FLW-REV-026`がPASS 4.96・P0〜P3全0件で`FLW-GATE-005`を通過した
  翌日に`FLW-REV-027`がFAIL 2.12となった事象は、設計レビューの高評価を production 経路の
  実行可能性と同一視したために生じた。本要件は、その同一視を機械的に禁止する。
  適用対象は`status: active`へ遷移する（＝Design Gate を通過する）bitz-flow の規範設計とする。
- **受入基準 (EARS)**:
  - WHEN 規範設計をDesign Gateへ提出する THEN bitz-flowは垂直接続図、状態遷移意味表、crash-point表、liveness budget表、platform reality表、legacy exclusion表の6表を当該設計成果物へ含めること SHALL
  - WHEN 垂直接続図の各行を検査する THEN bitz-flowはproduction入口、経由component、最終永続証跡、利用者出力、所有task、production test IDを各行へ明記すること SHALL
  - WHEN 垂直接続図の行がproduction test IDを名指しする THEN bitz-flowは当該testが実在し、production既定dispatcherを起点とすることを確認すること SHALL
  - WHEN 垂直接続図の行のproduction接続が未実装である THEN bitz-flowは当該行のtest ID欄へ`未実装`と記載し、実在しないtest IDまたはfixture注入testを記載しないこと SHALL
  - WHEN 状態遷移意味表を検査する THEN bitz-flowは`DONE`、`QUARANTINED`、`INDETERMINATE`、`BLOCKED`の各状態について前提、永続証跡、許される後続処理、禁止される完了判定を明記すること SHALL
  - WHEN crash-point表を検査する THEN bitz-flowは各durable writeの直前・直後で停止した場合の観測状態、authority、再開処理、重複実行時の結果を明記すること SHALL
  - WHEN liveness budget表を検査する THEN bitz-flowはchild単位とoperation全体のdeadline、kill手順、出力回収、terminal resultの最大応答時間を数値で明記すること SHALL
  - WHEN platform reality表を検査する THEN bitz-flowは対象OSごとの実装component、identity、probe方法、未対応時の即時拒否を明記し、他OSのcomponentによる代替を同一証明として扱わないこと SHALL
  - WHEN legacy exclusion表を検査する THEN bitz-flowは廃止した入力、field、context、approval方式がproduction入口から到達不能であることと、その到達不能性を確認するnegative test IDを明記すること SHALL
  - WHEN design GateのGatePassageを起票する THEN bitz-flowは接続完全性、失敗原子性、有限収束性、platform実在性、証跡妥当性、legacy排除、状態意味保存の7観点それぞれへ`実証済み`または`未実装境界`もしくは`検証計画`のいずれかを記録すること SHALL
  - WHEN 7観点のいずれかが`実証済み`でない THEN bitz-flowは当該観点をDesign GateのPASS根拠にせず、未実装境界または検証計画として明示すること SHALL
  - WHEN 設計成果物が接続を成立済みと表記する THEN bitz-flowはtest fixture上の接続または予定上の接続をその根拠にしないこと SHALL
- **検証手段**: `tests/test_flow_design_completion_contract.py`が`.spec/design/*.md`のうち
  `status: active`のものと`.spec/gates/*.md`のうち`gate: design`のものを動的収集し、6表の実在、
  各表の必須列、垂直接続図が参照するproduction test IDの実在、GatePassageの7観点記録を検査する。
  test IDの実在検査は`tests/`配下の収集結果と照合する。
- **Revision History**:
  - 1.1 (2026-08-24) 是正期間中の未実装行を`未実装`表記で許容し、架空test IDとfixture注入testの記載を禁止する形へ精密化
  - 1.0 (2026-08-24) FLW-REV-027の振り返り§5-§6を規範化してdraft起票（裁定参照: .spec/reports/decision-2026-08-24-flw-rev-027-remediation.md）
