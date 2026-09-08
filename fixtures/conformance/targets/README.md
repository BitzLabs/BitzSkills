# Target展開の期待集合

設計・検証日: 2026-09-08。
正本は[関係・トレースモデル §6.4](../../../docs/03.詳細設計/02_SPECモデル/04_関係・トレースモデル.md#64-targetexpansionroot-purpose)。

## 入力と期待値

`cases.json`は索引で解決済みの小さなgraph、起点、purpose、固定期待値を持つ。単一は非修飾、連合は修飾IDを使う。
`cases.schema.json`は未知field・期待配列の重複を拒否する。根拠契約のhashを固定し、変更時は期待値の再レビューを要求する。
GraphはREQ/TECH approved、ADR accepted、TASK open/doneに限定する。適用不能状態の診断は既存適合matrixの別ケースで扱う。

REQ、規範文ありTECH、規範文なしTECH、statement、TASK、ADRの6種類×3 purposeを18基本ケースで固定した。
ADRのimplement/verifyはcontext CLIの拒否期待であり、TargetExpansionがエラーobjectを返すというAPI追加ではない。
成功ケースの4配列はrootDocuments、contextDocuments、targetStatements、adjacentStatementsで、要素・順序を完全比較する。
interpretのtargetStatementsは空である。statement起点では指定句以外の兄弟句をadjacentとする。

## 追加7ケース

| ケース | 確認内容 |
|---|---|
| REFINEMENT-TRANSITIVE | 推移的refinementはtarget、requires先はContextだけ、relatedは追加しない |
| STATEMENT-ADJACENT | 指定句とrefinementだけtarget、兄弟句はadjacent |
| MULTI-ROOT-DEDUP | 文書・句・重複起点の和集合、targetへ選ばれた句をadjacentから除外 |
| TASK-REQUIRES-NOT-TARGET | 起点TASKのaddresses先だけ対象義務、先行done TASKのaddressesを義務へ追加しない |
| OPEN-TASK-IMPLEMENT | implementで対象句をaddressesするopen TASKをContextへ追加 |
| FEDERATED-SAME-LOCAL-ID | 同名local IDをworkspace別に区別し、横断refinementを対象へ追加 |
| SOURCE-LINE-ORDER | ID辞書順よりsource line順を優先 |

`matrixFamilies`は関連する論点の索引であり、そのfamilyの全適合試験を完了したという意味ではない。
このgraph fixtureはrepo/manifest/expected公開結果を持つ311件の適合fixtureを置き換えない。
規範文なしTECHの4集合は確認するが、文書単位bindingの保持・共有commandの実行回数・target別証跡はverify適合試験で確認する。

## 検証

`uv run fixtures/validate_step0b.py`から`target_vectors.py`を実行する。
固定期待値を検証用reference graph計算と照合し、入力graph・起点・関係・statement配列を反転しても一致することを検査する。
Schema、18組合せの網羅、ID/型・参照存在、強い依存の非循環、matrix family参照、根拠契約のhashも検査する。
回帰試験では組合せ欠落、requires先のtarget混入、順序誤り、未知参照を検出する。
期待値を実行中に再生成・更新しない。referenceはこの固定graphの準備検証用であり、製品Parserや完全なContext Resolverではない。
CoreのJSON出力、状態判定、binding、Digestとの一致はGate Bで別途検証する。
