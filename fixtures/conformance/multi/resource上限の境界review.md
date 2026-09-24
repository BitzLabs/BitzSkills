# resource上限の境界 fixture review

[適合fixture仕様 §7](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#7-最小matrix-複合workspace)の
`MULTI-020-01..16`と`MULTI-021-01..08`を扱う。いずれもreview済みの期待値であり、Coreの挙動を観測したものではない。

## 入力はcommitせず、dataset manifestから生成する

8つのdimensionの`limit - 1`、`limit`、`limit + 1`を実treeとしてcommitすると、repositoryは1 GiBを超える。
[ADR-048](../../../docs/02.設計書/10_決定記録/ADR-048_適合fixtureの生成入力とGit構造operationを確定する.md)に従い、
各fixtureは`repo/`の代わりにdataset manifestを持ち、`setup.generate.treeDigest`で生成treeを固定する。
期待結果と副作用期待値も生成物なので、`expect.resultDigest`と副作用の`stateDigest`で固定する。
reviewの対象は生成器（`multi_generator.py`）とdataset manifestである。

生成器は、狙ったdimensionだけを指定値にし、ほかを通常規模へ保つ。dataset manifestは8つのdimensionの
実測値をすべて持ち、監査は「狙った以外のdimensionが上限を超えていないこと」をその実測値から確かめる。
計数（`count`）は生成計画を読まず、生成したbyte列だけから数え直す。

## 入力側の上限とぶつけない

生成物は、[安全な入出力・互換性 §4](../../../docs/03.詳細設計/00_共通契約/02_安全な入出力・互換性.md)の
入力上限（設定64 KiB、SPEC 1 MiB、1文書の配列項目と規範文1,000件）を越えない形に分けている。

- commandはworkspaceあたり800件までに分け、10,000件の定義には13 workspaceを使う。
- 100万件のrelation edgeは1,000件ずつ別文書へ置き、targetは同じworkspaceの実在文書にする。
- 100万件のtrace項目はTASKの`changes`へ1,000件ずつ置く。`changes`は字句の許可集合なので、pathの実在を要求しない。
- 256 MiBの入力は、1 MiB未満の補充文書を並べ、最後の1件でちょうどの値に合わせる。

規範文はTECHの`Contract` sectionへ置く。[文書種別・本文template §3](../../../docs/03.詳細設計/02_SPECモデル/03_文書種別・本文template.md)が
他sectionの規範行を`SPEC-STYLE-PLACEMENT-001`とするためである。

## 越える側は早期に停止する

`MULTI-021-*`は`SPEC-MULTI-LIMIT-001`／`blocked`／終了コード2を返し、`workspaces: []`でmember処理もcommand実行も
始めない。`evidence`は`dimension`、`limit`、`observedAtLeast`を持つ。`observedAtLeast`は越えたことがわかる
最小の値（`limit + 1`）とし、正確な総数を求めない。

`MULTI-021-08`だけは、`verifyBindingCount`がcommand定義の部分集合であるため`commandDefinitionCount`も
同時に超える。複合workspace仕様 §10へ「複数のdimensionが同時に超過する場合は、verify実行計画のdimensionを
優先して報告する」を加え、dataset manifestの`companionDimensions`へ同時に超えるdimensionを明示した。
監査は、宣言していないdimensionの超過を拒否する。

## 検証は2段階に分ける

既定の統合検証（`uv run fixtures/validate_conformance.py`）は、同じdataset manifestを一定比率で縮小したprofileで
生成器の決定論とdimensionの計数を照合する。上限も同じ比率で縮めるので、越える／越えないの関係は保たれる。
実寸の生成、tree digest、期待結果のdigest、副作用のstate digestの照合は`uv run fixtures/validate_scale.py`が行い、
Gate Aの認定にはその記録を必要とする。

## 限界

- Coreは実行していない。実際に上限で遮断するか、境界内を通すかはGate Bで判定する。
- 期待結果は生成物であり、digestで固定する。人が読むのは生成器とdataset manifestである。
- 1つのfixtureは1つのdimensionだけを越える。全dimensionを同時に最大化した入力は扱わない。
- 基準環境でのpeak RSS 1 GiB以下という受入条件は、Coreの実行を伴うためGate Bで測定する。
