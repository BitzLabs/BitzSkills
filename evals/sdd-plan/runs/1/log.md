# 発動判定テスト run 1

- 実行日時: 2026-07-16
- ケース: ../../cases.md の T1〜T9（提示順 T1→T9、スキル一覧はアルファベット順）
- 実行方法: fast-worker（Sonnet）サブエージェントにスキル一覧（bitz-sdd 全13スキルの
  name + description）と発話9件を渡し、発話ごとに最初に発動すべきスキルを独立判定させた。
  期待解・テスト対象スキルは判定者に伏せた。

## 結果: 9/9 PASS

| ID | 発話 | 期待 | 判定 | 合否 |
|---|---|---|---|---|
| T1 | 次に何をすべきか教えて | sdd-plan | sdd-plan | ✅ |
| T2 | 現状把握したい。いまどのフェーズにいる？ | sdd-plan | sdd-plan | ✅ |
| T3 | どこまで進んだ？ | sdd-plan | sdd-plan | ✅ |
| T4 | 進捗を教えて | sdd-report | sdd-report | ✅ |
| T5 | 進捗レポートを出力して | sdd-report | sdd-report | ✅ |
| T6 | この要望を spec-issue にして | sdd-issue | sdd-issue | ✅ |
| T7 | 要望がいくつか溜まってるので整理して起票して | sdd-issue | sdd-issue | ✅ |
| T8 | 要件 SDD-FR-100 を廃止（deprecated）にしたい | sdd-core | sdd-core | ✅ |
| T9 | 承認済み要件をタスクに分解して | sdd-implement | sdd-implement | ✅ |

判定根拠（判定者出力の要旨): T1〜T3 は sdd-plan のトリガー語に直接一致、T4/T5 は
sdd-report の従来トリガーが維持され sdd-plan に奪われず、T8 は「要件の廃止・番号管理は
sdd-core の管轄」の記述を根拠に sdd-issue へ誤爆しなかった。
