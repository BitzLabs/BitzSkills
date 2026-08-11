# 裁定記録 — `SI-FLW-036` 全採点 proxy の棚卸し

- **日付**: 2026-08-11
- **裁定者**: ユーザー（本セッション）
- **対象**: `SI-FLW-036`
- **裁定の形式**: 対話で詳細計画を確認後、ユーザーが「進めましょう」と明示した。
  記録経路は代行可視化経路（`--on-behalf-of user --decision-ref`）。
- **裁定**: **accept**。2 trial の個別是正に限定せず、採点に使う全 proxy を一度に棚卸しする。

## 採用する範囲

1. 観測生成、trial 判定、集計、自己診断の4層について、採点に使う全 proxy を列挙する。
2. 各 proxy の measurand、母集団、oracle、選択・除外規則、乖離条件、歯止め、証跡を
   `FLW-DSN-014` に記録する。
3. result envelope の抽出を共通化し、先頭行固定を廃止する。ただし envelope が無い出力や
   task と異なる envelope を成功にしない。
4. compact 出力の truncation を契約として扱い、全量時は全 item、正当な省略時は集計値・
   `shown`・`total`・表示済み item の整合を検査する。
5. 既存の保存済み trial を再実測せず再採点し、規則変更前後の差分を
   `scoring_rule_version` で追跡可能にする。

## 歯止め

- `truncated: false` の全件検査を緩めない。
- envelope 探索は result code だけでなく operation も照合し、曖昧な複数候補を自己診断へ出す。
- proxy ごとに true positive、false positive 防止、false negative 防止の回帰を持つ。
- 配布物、fixture、被測定物の挙動は変更しない。変更範囲は設計文書、評価 harness、採点規則、
  回帰テスト、再採点記録に限定する。

## 要件化とゲート

採点規則と測定契約を変更するため軽量レーンは使わず、新規要件を draft 起票し、人間の approve と
Design Gate を経て実装する。既存 `FLW-NFR-001` / `FLW-NFR-008` の閾値は変更しない。

## 要件承認

- **対象要件**: `FLW-NFR-009`
- **裁定**: **approve**
- **裁定根拠**: 要件の目的、6つの受入基準、既存要件との責務分離、非変更範囲を説明した後、
  ユーザーが「OKです」と明示した。
- **記録経路**: 代行可視化経路
  （`--on-behalf-of user --decision-ref .spec/reports/decision-2026-08-11-si-flw-036-proxy-inventory.md`）。

## Design Gate裁定

- **対象**: `FLW-NFR-009` / `FLW-DSN-014` v1.13 / `FLW-REV-007`
- **レビュー証跡**: `FLW-REV-007` — PASS、集計4.88、今回範囲の未解決finding 0件
- **裁定**: **通過を承認**
- **裁定根拠**: 設計内容、レビュー結果、`spec inspect --check-only` PASSを提示後、
  ユーザーが「承認します」と明示した。
- **記録経路**: GatePassageを代行起票し、裁定者を`user`として記録する。
