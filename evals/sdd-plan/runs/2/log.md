# 発動判定テスト run 2（シャッフル再実行）

- 実行日時: 2026-07-16
- ケース: ../../cases.md の T1〜T9（発話提示順・スキル一覧提示順を run 1 からシャッフル）
- 実行方法: run 1 と同じ（独立の fast-worker サブエージェント。判定の再現性確認）

## 結果: 9/9 PASS（run 1 と全件一致）

| 提示順 | ID | 発話 | 期待 | 判定 | 合否 |
|---|---|---|---|---|---|
| 1 | T8 | 要件 SDD-FR-100 を廃止（deprecated）にしたい | sdd-core | sdd-core | ✅ |
| 2 | T5 | 進捗レポートを出力して | sdd-report | sdd-report | ✅ |
| 3 | T9 | 承認済み要件をタスクに分解して | sdd-implement | sdd-implement | ✅ |
| 4 | T1 | 次に何をすべきか教えて | sdd-plan | sdd-plan | ✅ |
| 5 | T6 | この要望を spec-issue にして | sdd-issue | sdd-issue | ✅ |
| 6 | T3 | どこまで進んだ？ | sdd-plan | sdd-plan | ✅ |
| 7 | T2 | 現状把握したい。いまどのフェーズにいる？ | sdd-plan | sdd-plan | ✅ |
| 8 | T7 | 要望がいくつか溜まってるので整理して起票して | sdd-issue | sdd-issue | ✅ |
| 9 | T4 | 進捗を教えて | sdd-report | sdd-report | ✅ |

総合判定: 2回独立実行で 18/18 一致。description の発動精度に衝突・誤爆なし。
