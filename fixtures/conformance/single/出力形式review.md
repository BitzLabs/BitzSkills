# 出力形式fixtureレビュー

2026-09-14。SINGLE-075-01/02とSINGLE-127-12を追加する。
根拠は[結果契約 §7・§8](../../../docs/03.詳細設計/00_共通契約/01_結果・Diagnostic・終了コード.md#7-textとjson)、
[CLI基盤契約 §7](../../../docs/03.詳細設計/00_共通契約/06_Core実行環境・CLI基盤契約.md#7-report-flag)、
[適合fixture仕様 §4](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#4-共通normalizer)と各matrix ID。

| ID | 実行の違い | 期待 |
|---|---|---|
| SINGLE-075-01 | 成功checkを明示text出力 | passed／0、要約1行、reportなし |
| SINGLE-075-02 | 参照切れcheckを明示text出力 | failed／1、要約とDiagnosticの2行、reportなし |
| SINGLE-127-12 | 成功checkでjsonとreportを併用 | passed／0、標準出力JSONと規定先report 1件 |

075の入力・完全期待JSONはSINGLE-070-01/02と同一で、formatだけを変更する。
manifestはtextFileとresultFileの双方を参照し、後者は表示と対応するJSON結果の期待値を保持する。
textにJSON本文を追加出力する指定ではない。各Gate Bでは同じsetupのJSON操作との一致も確認する。
要約のtargetsはcheckedDocumentCountの3、diagnosticsは成功0・失敗1。status、scopeと件数を省略しない。
失敗はTECH-001のrequires先TECH-999だけが不在で、Diagnosticのline/columnは未付与なので空fieldを保持する。
suggestedActionは存在しないため継続行を出さない。期待textはUTF-8、LF、末尾改行あり。
所要時間は0を代表値とし、共通契約のASCII duration tokenだけを比較時に正規化する。
status、件数、空field、改行、非ASCII数字や小数表記を正規化して隠さないことを回帰試験で確認する。

127-12はSINGLE-071-01と同じ物理入力・期待JSON・副作用期待値を独立directoryに持つ。
両optionを受理し、既存reportを保持したまま規定directoryへ1件だけ追加する。
出力形式がreportを暗黙生成しないことは075と既存070、reportを禁止しないことは127-12で確認する。

各fixtureのSchema・期待値・入力byte列、2回の隔離setupと固定snapshot一致を検査する。
textの件数改変、JSON statusの改変、副作用許可の拡大を拒否する回帰試験を追加する。
Coreは実行せず、text rendererも実装しない。実stdout、実report内容、実副作用の受入はGate Bで行う。
