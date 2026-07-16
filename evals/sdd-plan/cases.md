# 発動判定テストケース: sdd-plan / sdd-issue（縮小版トリガーテスト）

- 対象: bitz-sdd v1.10.0 の新スキル sdd-plan / sdd-issue の description 発動精度
- 種別: 発動判定のみ（skill-tester の3種別のうち「発動判定」に限定した縮小版。
  スキルあり/なし比較は省略 — 両スキルは既存スクリプトの案内層であり効果測定は過剰と裁定）
- 方法: bitz-sdd 全10スキルの name + description 一覧を判定材料として新しいセッション
  （fast-worker サブエージェント）に渡し、発話ごとに「最初に発動すべきスキル」を選ばせる。
  独立2回実行（発話・スキル一覧の提示順をシャッフル）し、2回とも期待どおりなら PASS。
- 記録: runs/<n>/log.md。関連ケース T6〜T8 は evals/sdd-issue/ からも本ファイルを参照する。

## ケース一覧

| ID | 入力プロンプト（ユーザー発話） | 期待スキル | 合格基準（アサーション） |
|---|---|---|---|
| T1 | 次に何をすべきか教えて | sdd-plan | 判定者が sdd-plan を選ぶ |
| T2 | 現状把握したい。いまどのフェーズにいる？ | sdd-plan | 同上 |
| T3 | どこまで進んだ？ | sdd-plan | 判定者が sdd-plan を選ぶ（sdd-report 誤爆しない） |
| T4 | 進捗を教えて | sdd-report | 従来トリガーが sdd-plan に奪われない |
| T5 | 進捗レポートを出力して | sdd-report | 同上 |
| T6 | この要望を spec-issue にして | sdd-issue | 判定者が sdd-issue を選ぶ |
| T7 | 要望がいくつか溜まってるので整理して起票して | sdd-issue | 同上 |
| T8 | 要件 SDD-FR-100 を廃止（deprecated）にしたい | sdd-core | 要件ライフサイクル操作が sdd-issue に奪われない |
| T9 | 承認済み要件をタスクに分解して | sdd-implement | 対照ケース（既存ルーティングの非破壊確認） |
