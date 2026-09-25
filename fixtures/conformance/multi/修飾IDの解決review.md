# 修飾IDの解決 fixture review

[適合fixture仕様 §7](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#7-最小matrix-複合workspace)の
`MULTI-001`、`MULTI-003`、`MULTI-004-01/02`、`MULTI-025-01/02`を扱う。いずれもreview済みの期待値であり、
Coreの挙動を観測したものではない。

## 4つの結末を1つずつ切り分ける

修飾IDの参照は、似た入力から異なるDiagnosticになる。そのため同じcorpusの変種を使い、1 fixtureにつき
1つの結末だけを起こす。

| fixture | 入力 | 結末 |
|---|---|---|
| `MULTI-001` | 2つのmemberが同じlocal ID `TECH-010`を持つ | 衝突しない。`passed` |
| `MULTI-003` | `web::TECH-010`が`REQ-001`を非修飾で参照する | `SPEC-MULTI-REF-001`（条件`MULTI-REF-UNQUALIFIED`） |
| `MULTI-004-01/02` | `web::TECH-010`が`api::TECH-999`を参照する | `SPEC-RELATION-MISSING-001` |
| `MULTI-025-01/02` | 起点に`api::REQ-009`を指定する | `CTX-ROOT-MISSING-001` |

`MULTI-003`と`MULTI-004`の違いはworkspaceの存在ではなく、修飾したかどうかである。`MULTI-003`の`REQ-001`は
`web`に存在せず`platform`にだけ存在する。Coreは非修飾IDを別workspaceから探索しないので、これは解決失敗ではなく
修飾の誤りとして扱う。`MULTI-004`の`api::TECH-999`は、workspace `api`が実在し文書だけがない。
どちらの変種にも、もう一方のcodeを起こす入力を置いていない。監査は入力からこれを確かめ、
散文の主張に頼らない。

`MULTI-003`の変種では`web::TECH-010`の`implements`と`tests`を外した。非修飾の`refines`を残したまま
`covers`を宣言すると、修飾の誤りに加えて所有境界または解決失敗という2つ目の原因が同じfixtureへ入るためである。
そのぶんwebのcodeとtestもcorpusから外し、宣言のないpathを置かない。

## 不在の起点は終了コード4と区別する

`--workspace`にcatalog外のIDを渡す場合はinvocation errorで終了コード4、操作結果もreportも作らない
（[複合workspace仕様 §3](../../../docs/03.詳細設計/02_SPECモデル/05_複合workspace仕様.md#3-workspace決定)）。
一方`MULTI-025-01/02`は、catalogにあるworkspaceを修飾に使い、その中に存在しない文書を起点に指定する。
こちらは操作結果を返す`CTX-ROOT-MISSING-001`／`failed`／終了コード1であり、`source`は`invocation`、
`argument`は指定したままの`api::REQ-009`とする。checkでは最上位のDiagnostic、verifyでは当該targetの
Diagnosticへ置き、commandは実行しない。監査試験は、この2件を終了コード4へ置き換えた写しと、
verifyのtarget Diagnosticを最上位へ移した写しを拒否する。

## 件数はworkspaceごとの実数とする

`check --all-workspaces`はcatalogの全SPECを完全検査するので、`checkedDocumentCount`は
`platform` 1件、`api` 1件、`web` 1件、`checkedStatementCount`は`platform`だけが2件になる。
`MULTI-004-02`は明示targetのworkspace単独checkであり、`TargetExpansion(web::TECH-010, interpret)`の
Contextに入る`platform::REQ-001`も完全検査するため2文書2句を数える。結果の`workspace`は
複合workspace内でも実際のworkspace IDとrepository root相対pathを返し、`multiWorkspace`外形は使わない。

## 限界

- Coreは実行していない。Diagnosticの文面と、検査した文書数の実際の値はGate Bで判定する。
- 修飾ID構文不正（条件`MULTI-REF-QUALIFIER`）と未知workspaceの修飾（`MULTI-REF-WORKSPACE`）は、
  この群では扱わない。`SPEC-MULTI-REF-001`の3条件のうち固定したのは`MULTI-REF-UNQUALIFIED`だけである。
- `MULTI-004-01`は完全解決が成立しないので空のBundleを返す。到達workspaceはrequest workspaceの1件だけとし、
  `resolution.workspaces`を1件以上とする規定を満たす最小の値をreview済みの期待値とした。

## 2026-09-26追記: MULTI-003とMULTI-004-01/02へevidenceを追加

2026-09-25に管理者が承認した方針を反映したcommitで、結果契約 §4とregistry §2へ、relation edgeを単位とする
Diagnosticが宣言どおりの参照先文字列を`evidence`に持つことが明記された。本reviewが扱う2条件も対象である。

- `MULTI-003`（`SPEC-MULTI-REF-001`）は、`web::TECH-010`が非修飾で宣言した`refines: [REQ-001]`の宣言どおりの
  文字列`"REQ-001"`を`evidence`として追加する。
- `MULTI-004-01`（context、`SPEC-RELATION-MISSING-001`）と`MULTI-004-02`（check、同code）は、`web::TECH-010`が
  宣言した`requires: [api::TECH-999]`の宣言どおりの修飾文字列`"api::TECH-999"`を`evidence`として追加する。

source（workspace/path/key）は変えていない。期待Diagnosticを増やす変更であり、比較の範囲を狭める緩和には
当たらない（[適合fixture仕様 §1.1](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#11-matrixとfixtureの変更)）。
