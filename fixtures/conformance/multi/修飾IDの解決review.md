# 修飾IDの解決のfixtureのレビュー記録

[適合fixture仕様 §7](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#7-最小matrix-複合ワークスペース)の
`MULTI-001`、`MULTI-003`、`MULTI-004-01/02`、`MULTI-025-01/02`を扱う。いずれもレビュー済みの期待値であり、
Coreの挙動を観測したものではない。

## 4つの結末を1つずつ切り分ける

修飾IDの参照は、似た入力から異なる診断になる。そのため、同じcorpusを少しずつ変えたものを使い、1つのfixtureにつき
1つの結末だけを起こす。

| fixture | 入力 | 結末 |
|---|---|---|
| `MULTI-001` | 2つのメンバーが同じローカルID`TECH-010`を持つ | 衝突しない。`passed` |
| `MULTI-003` | `web::TECH-010`が`REQ-001`を非修飾で参照する | 診断`SPEC-MULTI-REF-001`（条件`MULTI-REF-UNQUALIFIED`） |
| `MULTI-004-01/02` | `web::TECH-010`が`api::TECH-999`を参照する | 診断`SPEC-RELATION-MISSING-001` |
| `MULTI-025-01/02` | 起点に`api::REQ-009`を指定する | 診断`CTX-ROOT-MISSING-001` |

`MULTI-003`と`MULTI-004`の違いはワークスペースの存在ではなく、修飾したかどうかである。`MULTI-003`の`REQ-001`は、
`web`に存在せず、`platform`にだけ存在する。Coreは非修飾IDをほかのワークスペースから探索しないので、これは解決の失敗ではなく、
修飾の誤りとして扱う。`MULTI-004`の`api::TECH-999`は、ワークスペース`api`が実在し、文書だけがない。
どちらのcorpusにも、もう一方の診断コードを起こす入力を置いていない。監査は入力からこれを確かめ、
散文の主張に頼らない。

`MULTI-003`のcorpusでは、`web::TECH-010`の`implements`と`tests`を外した。非修飾の`refines`を残したまま
`covers`を宣言すると、修飾の誤りに加えて、所有境界または解決失敗という2つ目の原因が同じfixtureへ入るためである。
そのぶん、`web`のコードとテストもcorpusから外し、宣言のないパスを置かない。

## 不在の起点は終了コード4と区別する

`--workspace`にカタログ外のIDを渡す場合は、引数不正で終了コード4、操作の結果もレポートも作らない
（[複合ワークスペース仕様 §3](../../../docs/03.詳細設計/02_SPECモデル/05_複合workspace仕様.md#3-ワークスペースの決定)）。
一方`MULTI-025-01/02`は、カタログにあるワークスペースを修飾に使い、その中に存在しない文書を起点に指定する。
こちらは、操作の結果を返す診断`CTX-ROOT-MISSING-001`（`failed`）と終了コード1であり、`source`は`invocation`、
`argument`は指定したままの`api::REQ-009`とする。`check`では最上位の診断、`verify`では当該の検証対象の
診断へ置き、コマンドは実行しない。監査試験は、この2件を終了コード4へ置き換えた写しと、
`verify`の検証対象の診断を最上位へ移した写しを拒否する。

## 件数はワークスペースごとの実数とする

`check --all-workspaces`はカタログのすべての仕様文書を完全検査するので、`checkedDocumentCount`は
`platform` 1件、`api` 1件、`web` 1件、`checkedStatementCount`は`platform`だけが2件になる。
`MULTI-004-02`は、明示対象を指定した単独操作の`check`であり、`TargetExpansion(web::TECH-010, interpret)`の
コンテキストに入る`platform::REQ-001`も完全検査するため、2文書、規範文2件を数える。結果の`workspace`は
複合ワークスペース内でも、実際のワークスペースIDとリポジトリのルートからの相対パスを返し、`multiWorkspace`の外形は使わない。

## 限界

- Coreは実行していない。診断の文面と、検査した文書数の実際の値は、Gate Bで判定する。
- 修飾IDの構文の不正（条件`MULTI-REF-QUALIFIER`）と、未知のワークスペースによる修飾（`MULTI-REF-WORKSPACE`）は、
  この群では扱わない。診断`SPEC-MULTI-REF-001`の3つの条件のうち固定したのは、`MULTI-REF-UNQUALIFIED`だけである。
- `MULTI-004-01`は、完全解決が成立しないので、空のコンテキスト一式を返す。到達ワークスペースは起点ワークスペースの1件だけとし、
  `resolution.workspaces`を1件以上とする規定を満たす最小の値を、レビュー済みの期待値とした。

## 2026-09-26追記: `MULTI-003`と`MULTI-004-01/02`へ`evidence`を追加

2026-09-25に管理者が承認した方針を反映したコミットで、結果契約 §4と診断レジストリ §2へ、関係のエッジを単位とする
診断が、宣言どおりの参照先の文字列を`evidence`に持つことが明記された。このレビュー記録が扱う2つの条件も対象である。

- `MULTI-003`（診断`SPEC-MULTI-REF-001`）は、`web::TECH-010`が非修飾で宣言した`refines: [REQ-001]`の宣言どおりの
  文字列`"REQ-001"`を`evidence`として追加する。
- `MULTI-004-01`（`context`、診断`SPEC-RELATION-MISSING-001`）と`MULTI-004-02`（`check`、同じ診断コード）は、`web::TECH-010`が
  宣言した`requires: [api::TECH-999]`の宣言どおりの修飾文字列`"api::TECH-999"`を`evidence`として追加する。

`source`（ワークスペース、パス、キー）は変えていない。期待する診断を増やす変更であり、比較の範囲を狭める緩和には
当たらない（[適合fixture仕様 §1.1](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#11-matrixとfixtureの変更)）。
