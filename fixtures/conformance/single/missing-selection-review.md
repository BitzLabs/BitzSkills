# 起点・workspace不存在fixtureレビュー

2026-09-14。SINGLE-127-13とSINGLE-127-14を追加する。
根拠は[CLI基盤契約 §6](../../../docs/03.詳細設計/00_共通契約/06_Core実行環境・CLI基盤契約.md#6-targetとworkspaceの不存在)と
[適合fixture仕様](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md)の該当ID。

| ID | 唯一の不適合 | 期待 |
|---|---|---|
| SINGLE-127-13 | contextの構文上妥当な起点TECH-999が存在しない | failed／1、CTX-ROOT-MISSING-001 |
| SINGLE-127-14 | doctorの構文上妥当なworkspace `missing`が存在しない | 結果なし／4、標準エラー1行 |

SINGLE-127-13はSINGLE-050と同じ入力・完全期待結果を独立directoryへ保存する。
TECH-001が存在する有効なworkspaceでTECH-999だけを指定し、字句不正と混同しない。
失敗結果は要求したrootsを保持し、Digestはnull、resolution.completeはfalse、文書とLedgerは空とする。
Diagnostic sourceはinvocationのTECH-999。既知TECH-001への自動置換は許さない。
このケースは単一起点であり、複数起点の部分不在の継続契約は対象外。

SINGLE-127-14は既存の有効なSINGLE-042 corpusを使う。monorepo宣言がないためworkspace identityはrootだけであり、
`missing`は空stringでも不正な字句でもなく、探索後に不在と判定する。
SINGLE-127-07の空workspace値（探索前拒否）と区別し、Core操作の共通結果・statusは作らない。
標準出力なし、`bitz: doctor: <reason>`の標準エラー1行、理由必須・端末制御文字なしを固定する。
自然言語の理由文字列そのものは固定しない。

両件ともreport生成0件、repository・Git status/index・隔離HOME/cache/TMPDIRのbefore/after完全一致。
既存検証へ統合し、Schema・入力byte列・完全期待値・2回の隔離setupとsnapshot一致を確認する。
回帰試験はworkspaceのrootへの置換、両ケースの終了コード混同、失敗Contextのcomplete化とsource改変を拒否する。
これは準備証拠の検査であり、実際のworkspace探索・操作結果・副作用はCore実装後のGate Bで検証する。
