# 修飾IDの解決のfixtureのレビュー記録

[適合fixture仕様 §7](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#7-最小matrix-複合ワークスペース)の
`MULTI-001`、`MULTI-003`、`MULTI-004-01/02`、`MULTI-025-01/02`、`MULTI-027-01/02`を扱う。いずれもレビュー済みの期待値であり、
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
（[複合ワークスペース仕様 §3](../../../docs/03.詳細設計/02_仕様文書モデル/05_複合ワークスペース仕様.md#3-ワークスペースの決定)）。
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

## 2026-10-07追記: `MULTI-027-01/02`（他のメンバーの文書の`requires`の型制約）

### 追加の理由

状態が`accepted`でないADRへの`requires`を、状態の診断（`CTX-STATE-001`、`blocked`）ではなく型制約の
`CTX-RELATION-TYPE-001`（`failed`）で返すようにした是正（確認事項C17）を、独立したレビューで検分したところ、複合ワークスペースで
診断が出ない回帰が見つかった。是正の途中の版は、呼び出し側の関係の検査が見ない文書（複合ワークスペースの他のメンバーの文書）が
状態`proposed`のADRを`requires`しても、診断を返さず、成功としていた。是正前のCoreは、同じ入力で`blocked`／終了コード2の
`CTX-STATE-001`（`api`のADR-001）を返す。単一ワークスペースの`SINGLE-147`〜`149`には、他のメンバーの文書という場面がないので、
この回帰は押さえられていなかった。そこで、複合ワークスペースで同じ型制約を固定する2件を加える。

### 根拠の規範文

- 関係・トレースモデル §4: `requires`の参照先は、REQ、TECH、`accepted`のADRである。状態が`accepted`でないADRへの`requires`は、
  診断`CTX-RELATION-TYPE-001`とする。
- 関係・トレースモデル §6.3: コンテキストへ含めない閉包の文書と、複合ワークスペースの他のメンバーの文書については、閉包を構成する
  `requires`の型制約だけを検査し、それ以外の関係は検査しない。
- `context` §3: 状態の検査と強い関係の検査は、一方が非成功でも他方を行う。状態が`accepted`でないADRへの`requires`は、状態の検査ではなく
  型制約で扱う。
- 結果・診断・終了コード §4: 関係のエッジを単位とする診断は、宣言どおりの参照先を`evidence`に持つ。
- 複合ワークスペース仕様 §4: 診断の`source.path`は、`source.workspaceId`のワークスペースのルート相対とする。
- 複合ワークスペース仕様 §6・§7: 単独操作は、横断する関係の解決に必要な索引と到達先の解析を行うが、無関係なメンバーを完全検査しない。
  結果の`workspace`は起点ワークスペースである。

### 入力

ルートワークスペース`platform`（仕様文書なし）と、メンバー`web`（`apps/web`）、`api`（`services/api`）を、`MULTI-001`と同じカタログの形で置く。

| 文書 | 状態 | 内容 |
|---|---|---|
| `web`のREQ-001 | `approved` | `MUST`の規範文1件。`relations.requires: [api::TECH-020]`。`tests`は`tests/test_login.py`が`REQ-001:AC-01`を`covers`し、コマンド`frontend`で実行する |
| `api`のTECH-020 | `approved` | `relations.requires: [ADR-001]` |
| `api`のADR-001 | `proposed` | 状態が`accepted`でない判断 |

`web`のコードとテストは、`MULTI-027-02`の`verify`のテスト対応のために置く。2件は同じ入力を共有する。
`web`のREQ-001は`api`のTECH-020を型の表（REQ→TECH）のとおり`requires`し、TECH-020も`approved`なので、原因はTECH-020から
ADR-001への`requires`の1つだけである。TECH-020は`api`の文書で、呼び出し側のワークスペースは`web`なので、呼び出し側の関係の検査は
TECH-020を見ない。

| fixture | 操作 | 期待 |
|---|---|---|
| `MULTI-027-01` | `apps/web`で`context REQ-001 --purpose implement --format json` | `failed`／1 |
| `MULTI-027-02` | リポジトリのルートで`verify web::REQ-001 --format json` | `failed`／1 |

### 期待値の導き方

1. 起点`web::REQ-001`の`requires`の閉包をたどる。REQ→TECHは型の表を満たすので、`api::TECH-020`へ進む。
2. TECH-020の`requires: [ADR-001]`は、参照先が状態`proposed`のADRなので、型の表（`accepted`のADRだけを許す）に反する。診断は
   `CTX-RELATION-TYPE-001`（重大度`error`、`resultStatus: failed`）の1件とする。状態の診断にしないので、`CTX-STATE-001`は返さない。
3. 診断の発生元は、関係を宣言した文書である。`workspaceId`は`api`、`path`はメンバー相対の`.spec/technical/TECH-020.md`、
   `key`は`relations.requires`とする。`evidence`は、`api`の中で書いた修飾のない`ADR-001`とする。
4. `MULTI-027-01`の`resolution`は、完全解決が成立しないので`complete: false`、`documentCount: 0`、`unresolvedStrongRelations: 1`
   （返した`CTX-RELATION-TYPE-001`と`SPEC-RELATION-MISSING-001`の件数）とする。`contextDigest`は`null`、`documents`、制約台帳、
   カバレッジは空とする。最上位の`workspace`は起点の`web`、`roots`は修飾した`web::REQ-001`である。
5. `MULTI-027-02`は、同じ診断を検証対象`web::REQ-001`の`diagnostics`に1件置く。`contextDigest: null`、`statements: []`、
   `bindingRefs: []`、最上位の`commands: []`とし、テストを開始しない。最上位の`workspace`は`web`、最上位の`diagnostics`は空である。

監査は、この導出を`multi_relation_type_fixtures.reference_diagnostics`として、入力の木構造から独立に計算し、期待値と照合する。
型に反する辺がcorpus全体で1件だけで、`requires`以外の関係を宣言する文書がなく、診断の発生元が呼び出し側と異なる実在のメンバーで、
起点が定義済みのコマンドと実在のテストを持つことも、入力から確かめる。監査試験は、`CTX-STATE-001`への置換、診断を消した成功への改変、
発生元のワークスペースの改変、`evidence`の修飾、診断を最上位へ移した写しを拒否する。

### 固定しない範囲

- Coreは実行していない。診断の文面（`summary`）は比較に使わない。
- `MULTI-027-01`の`resolution.workspaces`は、`MULTI-004-01`と同じく起点ワークスペースの1件だけを期待値にした。複合ワークスペース仕様 §6は
  「1件以上」とだけ定め、完全解決が成立しない結果に、途中で到達した`api`を含めるかは定めていない。`crossWorkspaceEdges`も空とした。
  この点は、規範文の明記を待って固定する。
- `requires`以外の関係（`refines`など）が、他のメンバーの文書でどこまで検査されるかは固定しない。`verify`のTASK起点で、コンテキストへ
  含めない`requires`の閉包の文書の型制約は、単一ワークスペースの`SINGLE-149`が固定する。
- 他のメンバーの文書が複数の型制約違反を持つ場合の診断の順序は固定しない。
