# reportと結果外形の移行 fixture review

[適合fixture仕様 §7](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#7-最小matrix-複合workspace)の
`MULTI-022-01..04`、`MULTI-023-01..03`、`MULTI-024-01..03`を扱う。いずれもreview済みの期待値であり、
Coreの挙動を観測したものではない。

## 全体reportはroot workspaceへ1件だけ作る

`MULTI-022`は、checkとverifyのそれぞれで既定実行と明示`--report`を対にする。既定実行はstatusにかかわらず
fileを作らず、明示指定時だけroot workspaceの`.spec/reports/`へ1件を排他的に作成する。入力には
`.spec/reports/existing.json`を残す。空のdirectoryへ作るだけでは、排他的な作成と置換を区別できないためである。

対の2件は同じcorpusとcommit済み状態を使うので、結果本体は完全に一致しなければならない。監査はこれを
直接比較し、`--report`の有無で結果が変わる写しを拒否する。名前のpatternは、正しい形式を受理し、時刻の欠落、
0の連番、別操作名、残った`.tmp`接尾辞を拒否することを要求する。patternを`^.*$`へ緩めた写しも拒否する。

## dual-read consumerは排他的外形で識別する

`MULTI-023`はCore配布物の`bitz.compat`をconsumer runnerとして起動し、`result-shape <path>`で指定JSONを判定する。
判定は[結果・Diagnostic・終了コード §2](../../../docs/03.詳細設計/00_共通契約/01_結果・Diagnostic・終了コード.md#2-共通結果)の
排他的外形に従う。

| fixture | 入力JSON | outcome |
|---|---|---|
| `MULTI-023-01` | `workspace`あり、`multiWorkspace`／`workspaces`なし | `accepted` |
| `MULTI-023-02` | `workspace`なし、`multiWorkspace`と`workspaces`あり | `accepted` |
| `MULTI-023-03` | 両方あり | `rejected` |

監査は、受理するcaseのJSONが公開結果Schemaへ適合すること、拒否するcaseのJSONが適合しないことを、
Schemaそのもので確かめる。修飾IDの`::`、report file名、current directoryから種別を推測する入力は置かない。

## 移行は1つの原子的な変更集合として表す

`MULTI-024`のcase名と引数は本fixtureで確定した（[ADR-046](../../../docs/02.設計書/10_決定記録/ADR-046_適合harnessの検査対象・実行環境・runnerを確定する.md)が
作成時に固定すると定めている）。runnerは`to-multi-workspace`と`rollback`の2 caseを持ち、基準版（`HEAD`）と
現在版のtreeを比べる。

- `MULTI-024-01`: 基準版は単一workspace。1つの変更集合でcatalog、member設定、SPECの移動、修飾参照を同時に適用する。
- `MULTI-024-02`: 基準版は複合workspace。catalog、member設定、SPECの位置、参照をすべて単一workspaceへ戻す。
- `MULTI-024-03`: 同じrollbackだが、文書の修飾参照`platform::REQ-001:AC-01`だけが残る部分rollbackであり、
  `rejected`とする。

監査は、基準版のcatalogをGitのblobから読み、現在版のtreeと突き合わせて各caseが名乗るとおりの変更に
なっていることを確かめる。`MULTI-024-03`の修飾参照を非修飾へ直した写しは、部分rollbackの証拠ではなくなるので拒否する。

## 限界

- Coreは実行していない。`bitz.compat`の実装はGate Bで判定する。判定logicはfixture側に持たず、入力と
  期待するoutcomeだけを固定している。
- `MULTI-022`は成功する全体操作だけを扱う。保存先が使えない場合の`SPEC-REPORT-WRITE-001`は
  単一workspaceの`SINGLE-072`が所有する。
- `MULTI-024`はrollbackの可否を2件で固定する。forward fixを選ぶ判断、report成果物の系列分離は
  運用手順が所有し、fixtureでは扱わない。
