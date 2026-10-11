# 修飾IDの解決のfixtureのレビュー記録

[適合fixture仕様 §7](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#7-最小matrix-複合ワークスペース)の
`MULTI-001`、`MULTI-003`、`MULTI-004-01/02`、`MULTI-025-01/02`、`MULTI-027-01/02`、`MULTI-028`、`MULTI-029-01`〜`03`を扱う。いずれもレビュー済みの期待値であり、
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

## 2026-10-11追記: `MULTI-028`（TASKが他のメンバーの規範文のないTECHを`addresses`する`verify`）

### 追加の理由（実装の確認事項C5）

`addresses`の参照が規範文かどうかを`:`の有無で判定していたため、複合ワークスペースの修飾ID（`api::TECH-020`）を規範文と取り違え、
TASKが他のメンバーの規範文のないTECHを`addresses`する`verify`が、Coreの例外（`KeyError`）で失敗していた。修飾IDは、文書IDでも
`::`を含むので、`:`の有無では規範文と区別できない。修正後は、索引で規範文か文書かを判定する。単一ワークスペースの
`SINGLE-156`と`SINGLE-157`（上と[`done`のTASK起点のレビュー記録](../single/doneのTASKが起点のレビュー記録.md)）は`:`を含まない文書IDなので、
この取り違えを押さえられない。そこで、複合ワークスペースで同じ入力を固定する1件を加える。

### 根拠の規範文

- [ADR-026](../../../docs/02.設計書/10_決定記録/ADR-026_verifyのテスト割当て・タイムアウト・結果スキーマの確定.md)の`Decision`の7番目の項目、
  関係・トレースモデル §6.4の規則3、`verify` §3: 規範文のないTECHを`addresses`する場合は規範文を追加せず、そのTECHの文書単位の`tests`を実行対象へ含める。
- 複合ワークスペース仕様 §4: `relations`と`tests[].covers`は、別のワークスペースを参照するとき複合ワークスペースの正規形式（`api::TECH-020`）を必須とする。
  同じワークスペースを参照するときは非修飾形式を許可する。単独操作の結果は、`roots`、文書ID、`statements`、`covers`などを正規形式で返す。
- `verify` §4・§8: テスト割当ては所有ワークスペースとコマンド名の組（`api::backend`）で識別し、コマンドの実体は所有ワークスペースの設定で解決する。
  複合ワークスペースの中では、検証対象、規範文、`covers`のIDを修飾IDで返す。
- 関係・トレースモデル §6.3: 起点がTASKの場合は、その`addresses`の参照先と、その参照先を所有する文書を`contextDocuments`（ハッシュ値の材料の`documents[]`）へ含める。
- 複合ワークスペース仕様 §6・§7: 結果の`workspace`は起点ワークスペースである。
- コンテキストのハッシュ値の正規化仕様 §3: `workspaces`は到達ワークスペースを起点ワークスペースを先頭、以降を`id`の辞書順に並べ、設定の抽出は到達ワークスペースだけを対象にする。
  横断するエッジは`crossWorkspaceEdges`へ、宣言した強い関係は`strongRelations`へ置く。

### 入力と起動

ルートワークスペース`platform`（仕様文書なし）と、メンバー`web`（`apps/web`）、`api`（`services/api`）を、`MULTI-027`と同じカタログの形で置く。
リポジトリのルートで`verify web::TASK-001 --format json`を実行する。

| 文書 | 状態 | 内容 |
|---|---|---|
| `web`のTASK-001 | `open` | `relations.addresses: [api::TECH-020]`だけ |
| `api`のTECH-020 | `approved` | 規範文なし。`tests`は`tests/test_audit.py`が`TECH-020`（自身の文書ID）を`covers`し、コマンド`backend`で実行する |

`api`の設定は`backend`（`/bin/true {tests}`）だけを定義し、`web`の設定はコマンドを定義しない。コマンド名を起点のワークスペースで解決する実装は、
`web`に`backend`がなく失敗するので、所有ワークスペースでの解決を判別できる。原因は、TASKが別のメンバーの規範文のないTECHを修飾IDで
`addresses`することの1つだけである。

### 期待値の導き方（Coreの出力を根拠にしない）

| 項目 | 期待値 | 根拠 |
|---|---|---|
| 結果の状態／終了コード | `passed`／0 | テストは通る（`/bin/true`）。診断は置かない |
| `workspace` | `web`（`apps/web`） | 結果の`workspace`は起点ワークスペース（`MULTI-027-02`と同じ） |
| `targetResults[0].target` | `web::TASK-001` | 複合ワークスペースでは修飾ID |
| `statements` | `[]` | 関係・トレースモデル §6.4の規則3。`api::TECH-020`は規範文を持たないので、対象規範文を追加しない |
| `bindingRefs` | `["api::backend"]` | テスト割当ての所有者は、テストを宣言した文書を所有する`api`。コマンド名`backend`は`api`の設定で解決する（`verify` §4） |
| `commands` | 1件。`bindingId: api::backend`、`workspaceId: api`、`tests: ["tests/test_audit.py"]`、`argv: ["/bin/true", "tests/test_audit.py"]`、`covers: ["api::TECH-020"]`、`timeoutSeconds: 300`、`cwd: .` | `tests`は所有ワークスペース相対の宣言パス、`covers`は修飾ID（`verify` §8）、`timeoutSeconds`と`cwd`は`api`の設定の既定値 |
| `revision` | `{commit: 0×40, dirty: false}` | 複合ワークスペースは`null`にしない（結果・診断・終了コード §2）。`MULTI-027-02`と同じ準備 |
| `contextDigest` | `sha256:8678b52b4a826ee2a9c6658e58ccf9f105ba7eaf65714ec25cd7215d1b04163e` | 下の参照計算 |

`commands[]`は、選択した対象を1つのワークスペース（`web`）で実行する結果の最上位に置く。`api`が所有するテスト割当ての結果を、最上位の`commands[]`へ置き、
`workspaceId`で所有者を示すのは、`MULTI-002-02`（横断する具体化のテストを`api`と`web`が所有する`verify`）と同じ形である。`verify` §10は
`verify --all-workspaces`で所有ワークスペースのメンバーの結果へ置く形を定めるが、明示対象の単独操作で他のメンバーが所有するテスト割当ての置き場所は定めていない
（下の「固定しない範囲」を参照）。

`contextDigest`は、独立に書いた2系統の参照計算で導く。A（`verify_task_tech_fixtures.reviewed_digest_input`）はリテラルで書いた材料、
B（`multi_crosscheck.build`）は入力の木構造から導出した材料である。材料は、起点`web::TASK-001`と、`addresses`の先を所有する`api::TECH-020`の2文書
（`documents[]`は`api::TECH-020` < `web::TASK-001`）、到達した`web`と`api`の2ワークスペース（`workspaces[]`は起点の`web`が先頭）、横断するエッジ1件
（`addresses`、`web::TASK-001`から`api::TECH-020`）、`api`の`backend`とタイムアウト300秒の各1件を持つ。`web`は閉包にテスト対応を持つ文書がないので、
コマンドもタイムアウトも収録しない。ルートワークスペース`platform`は到達しないので材料へ入れない。参照計算Bは、TASK起点の`addresses`の先を距離1で閉包へ含める
規則（関係・トレースモデル §6.3）を`multi_crosscheck.closure`へ加えて導出した（`requires`を持つTASK起点は、辿らない辺の扱いが必要なため、この参照計算の対象外で拒否する）。
`statements`、`bindingRefs`、`commands`は、`reference_plan`が入力の木構造から導く計画とも照合する。

### 監査の検査と回帰試験

`verify_task_tech_fixtures.py`の`check_conditions`が、TASK-001が`open`で`api::TECH-020`だけを`addresses`すること、TECH-020が`approved`で規範文を持たず、自身の文書IDを
`covers`して`api`の設定が定義する`backend`を指すテスト対応を1件だけ持つこと、`web`がコマンドを定義しないこと、`api`が`backend`だけを定義することを、入力の木構造から確かめる。
`test_conformance_audit.py`の回帰試験は、`bindingRefs`・`commands`の消去、`statements`への規範文の追加、`bindingId`・`workspaceId`を`web`へ戻す改変、`covers`の修飾の消去、
`target`の修飾の消去、`workspace`と`revision`の改変、マニフェストの起点の差替え、入力の改変（TASKの`addresses`を非修飾にする、状態を変える、TECH-020の`tests`・`command`・`covers`を変える、
`web`に`backend`を足す、`api`の設定を変える）を拒否する。

### 固定しない範囲

- 修正前のCore（`targetexpand.py`と`verify.py`をコミット`88896f3a`の版へ戻したもの。作業ツリーの外のコピーで確認した）は、`KeyError: 'api::TECH-020'`の例外で失敗する
  （陰性対照。終了コードは1）。修正後のCoreは通る。
- 明示対象の単独操作で、他のメンバーが所有するテスト割当ての結果（`commands[]`）を、最上位に置くか、所有ワークスペースの結果に置くかは固定しない。`MULTI-002-02`の既存の形（最上位）に従った。
  規範文の明記を待って固定する。
- 規範文を持つTECHや、REQの規範文と規範文のないTECHが混在する`addresses`は、複合ワークスペースでは固定しない（単一ワークスペースの`SINGLE-157`が固定する）。
- 他のメンバーのTECHが具体化文書を持つ場合、`tests`を持たない場合、コマンドを解決できない場合は固定しない。
- Coreは実行していない（期待値を決めた後に、一致を確かめるためだけに実行した）。Coreとの一致の判定はGate Bで行う。

## 2026-10-11追記: `MULTI-029-01`〜`03`（引数なしの`check`、`--full`、`--workspace`の複合ワークスペース対応）

### 追加の理由（実装の確認事項C4）

`check`は、位置引数に修飾IDがあるときだけ複合ワークスペースの索引を使っていた。修飾IDのない引数なしの`check`と`--full`は、作業ワークスペースだけの索引で動き、
`api::TECH-020`や`platform::REQ-001:AC-01`のような修飾した参照を`SPEC-RELATION-MISSING-001`と誤検出した。結果の`workspace.path`も、メンバーの中で実行しても`.`だった。
`--workspace`は、最寄りの設定のIDと比べるだけで、ルートからメンバーを作業ワークスペースにできなかった（終了コード4になる）。
既存の複合ワークスペースの`check`のfixtureは、修飾IDを明示対象にする`MULTI-004-02`、`MULTI-009`、`MULTI-010`、`MULTI-025-01`か、全体操作の`--all-workspaces`であり、
引数なしと`--full`と`--workspace`の経路を押さえていなかった。そこで、3つの経路を1件ずつ固定する3件を加える。

### 根拠の規範文

- 複合ワークスペース仕様 §3: 複合ワークスペースでは、最寄りの`.spec/bitz.yaml`のワークスペースが作業ワークスペースになる。`--workspace <id>`は、カタログ内のIDで作業ワークスペースを
  置き換える。
- 複合ワークスペース仕様 §4: 単独操作の結果の`workspace`は実際のワークスペースIDとリポジトリのルート相対のパスで、診断の`source.workspaceId`は所有ワークスペースのID、
  `source.path`は所有ワークスペース相対である。`relations`は別のワークスペースを参照するとき修飾IDを必須とし、修飾IDは統合索引で解決する。
- 複合ワークスペース仕様 §6・§7: 単独操作は、横断する関係の解決に必要な索引と到達先の解析を行うが、無関係なメンバーを完全検査しない。
- `check` §3: 完全検査の対象は、`--full`ではすべての仕様文書、引数なしではGitの変更から選んだ所有文書、強い関係の閉包、直接の逆参照である。強い関係の閉包は4つの強い関係
  （`requires`、`refines`、`addresses`、`supersedes`）を前方へ推移的にたどる。直接の逆参照は、自身の`relations`（5種のどれでもよい）で、集合内の文書またはその規範文を1段で
  参照する文書である。
- `check` §6: 複合ワークスペースの単独操作では、作業ワークスペースが所有する変更されたパスだけを出発点にする。ワークスペースをまたぐ強い関係の閉包と直接の逆参照は
  通常どおり辿るが、別のワークスペースの無関係な変更を対象へ混ぜない。
- `check` §9: `scope: changed`は`selection`（`changedPathCount`、`targetDocumentCount`、`excludedCodeTestPathCount`）を持ち、`scope: full`は`checkedDocumentCount`、
  `checkedStatementCount`を持つ。
- 結果・診断・終了コード §4・§7: 関係のエッジを単位とする診断は、`evidence`に参照先を宣言どおりの文字列（所有ワークスペースの中で書いた形）で持つ。診断は発生元のワークスペースID、
  `path`の順に並べる。
- ADR-035: `targetDocumentCount`は、パスを所有する文書のIDへ正規化し、重複排除した後の文書の数である（下の「固定しない範囲」を参照）。

### 入力と起動

3件とも、ルートワークスペース`platform`と、メンバー`web`（`apps/web`）、`api`（`services/api`）を、`MULTI-001`と同じカタログの形で置く。状態は、`MULTI-029-03`の`api::TECH-040`を除いて
すべて`approved`である。

`MULTI-029-01`と`MULTI-029-02`は同じ入力（変更集合なし）を共有する。

| 文書 | 内容 |
|---|---|
| `platform`のREQ-001 | `MUST`の規範文1件（`REQ-001:AC-01`） |
| `web`のTECH-010 | `requires: [api::TECH-020]`、`refines: [platform::REQ-001:AC-01]` |
| `web`のTECH-011 | 関係なし（閉包に含まれない`web`の文書） |
| `api`のTECH-020 | 関係なし（閉包で到達する他のメンバーの文書） |
| `api`のTECH-050 | `requires: [TECH-998]`（存在しない参照。`web`と無関係） |

| fixture | 実行ディレクトリ | 引数 |
|---|---|---|
| `MULTI-029-01` | `apps/web` | `check --full --base HEAD --format json` |
| `MULTI-029-02` | リポジトリのルート | `check --workspace web --full --base HEAD --format json` |

`MULTI-029-03`は、`web`のTECH-030の本文を変更し（準備手順の`update`。基準版のコミットは変更前）、`apps/web`で`check --base HEAD --format json`（引数なし）を実行する。

| 文書 | 内容 | 位置づけ |
|---|---|---|
| `web`のTECH-030 | `requires: [api::TECH-020]`。本文を変更する | 変更した文書（出発点） |
| `api`のTECH-020 | `requires: [TECH-999]`（存在しない） | 強い関係の閉包で到達する他のメンバーの文書 |
| `api`のTECH-040 | 状態`draft`。`refines: [web::TECH-030]`、`requires: [TECH-997]`（存在しない） | 作業ワークスペースの文書を参照する、他のメンバーの文書（直接の逆参照） |
| `api`のTECH-060 | `refines: [TECH-020]`、`requires: [TECH-996]`（存在しない） | 閉包で到達した他のメンバーの文書の逆参照 |
| `api`のTECH-050 | `requires: [TECH-998]`（存在しない） | 無関係な文書 |

4件の`api`の文書は、いずれも存在しない参照を1件だけ持つ。診断の有無で、完全検査の対象になったかどうかを見分けられる。

### 期待値の導き方（Coreの出力を根拠にしない）

`MULTI-029-01`／`02`（`scope: full`）。

1. 作業ワークスペース: `029-01`は`apps/web`の最寄りの設定の`web`（§3の2・3）。`029-02`は実行ディレクトリがルートで、最寄りの設定は`platform`だが、`--workspace web`が`web`へ置き換える（§3の5）。
   結果の`workspace`は`{id: web, path: apps/web}`である。
2. 完全検査の対象: `web`のすべての仕様文書（TECH-010、TECH-011）。`web::TECH-010`の強い関係の閉包は`api::TECH-020`（`requires`）と`platform::REQ-001`（`refines`の規範文の所有文書）。
   `api::TECH-020`と`platform::REQ-001`は関係を宣言しない。他のメンバーから`web`の文書を参照する文書はない。`api::TECH-050`は閉包にも逆参照にも入らない。
   `checkedDocumentCount`は4、`checkedStatementCount`は`platform::REQ-001`の1件である。
3. 診断: 修飾した参照（`api::TECH-020`、`platform::REQ-001:AC-01`）は統合索引で解決できる。完全検査の対象の文書に、存在しない参照はない。`api::TECH-050`の`TECH-998`は対象外なので返さない。
   診断は0件で、`passed`／終了コード0、`revision.dirty`は`false`である。

`MULTI-029-03`（`scope: changed`）。

1. 作業ワークスペースは`web`（`workspace`は`{id: web, path: apps/web}`）。変更集合は`apps/web/.spec/technical/TECH-030.md`の1件で、`web`が所有する。`revision.dirty`は`true`。
2. `selection`: `changedPathCount`は1、`targetDocumentCount`は1（`web::TECH-030`）、`excludedCodeTestPathCount`は0。
3. 完全検査の対象: 出発点`web::TECH-030`、強い関係の閉包で到達する`api::TECH-020`、`web::TECH-030`を`refines`する`api::TECH-040`（作業ワークスペースの文書の直接の逆参照）の3文書。
   `api::TECH-060`は閉包で到達した他のメンバーの文書の逆参照、`api::TECH-050`は無関係なので入れない。
4. 診断: `api::TECH-020`の`relations.requires`の`TECH-999`と、`api::TECH-040`の`relations.requires`の`TECH-997`の`SPEC-RELATION-MISSING-001`が各1件。`workspaceId`は`api`、`path`はメンバー相対
   （`.spec/technical/TECH-020.md`、`.spec/technical/TECH-040.md`）、`evidence`は宣言どおりの文字列。`web::TECH-030`の`api::TECH-020`は実在するので診断しない。順序は`workspaceId`、`path`の辞書順である。
   `failed`／終了コード1。

監査は、この導出を`multi_check_fixtures.reference_check`として、入力の木構造とGitの変更集合から独立に計算し、リテラルの期待値と照合する。作業ワークスペース、変更集合の所有判定、強い関係の閉包、
直接の逆参照、診断を別々に導く。入力が上の構成（誤りを持つ文書、閉包、逆参照、陰性対照の位置づけ）であることも、`check_conditions`が入力の木構造から確かめる。

### 監査の検査と回帰試験

`test_conformance_audit.py`の回帰試験は、修正前の誤検出（`SPEC-RELATION-MISSING-001`の混入）、`workspace`の改変（`path: "."`、`platform`、`api`）、`checkedDocumentCount`／`checkedStatementCount`の改変、
`scope`、`revision.dirty`、`selection`の各件数の改変、他のメンバーの診断の所有ワークスペースの改変、閉包の逆参照と無関係な文書の診断の混入、診断の消去と順序の入替え、マニフェストの改変
（実行ディレクトリ、`--full`と`--workspace`の削除、準備手順の変更の削除）、入力の改変（無関係な文書の誤りの除去、作業ワークスペースへの参照の追加、`draft`の除去、閉包の逆参照の付け替え、
二つ目の誤りの追加）を拒否する。

### 固定しない範囲

- 修正前のCore（コミット`82d60f2d`の`check.py`、`basecompare.py`、`multirelate.py`。作業ツリーの外のコピーで確認した）は、3件とも失敗する（陰性対照）。`MULTI-029-01`は`web::TECH-010`の
  `api::TECH-020`と`platform::REQ-001:AC-01`を`SPEC-RELATION-MISSING-001`と誤検出して`failed`、`workspace.path`は`.`、`checkedDocumentCount`は2になる。`MULTI-029-02`は終了コード4になる。
  `MULTI-029-03`は`workspace.path`が`.`で、`web::TECH-030`の`api::TECH-020`を誤検出し、`api`の2件の診断は返らない。修正後のCoreは通る。Coreの出力は期待値を決めた後に、一致を確かめるためだけに使った。
- `targetDocumentCount`が、変更したパスを所有する文書だけを数え、閉包や直接の逆参照で完全検査の対象に加わる文書を数えないことは、ADR-035の「パスを所有する文書のIDへ正規化し」と、
  `check` §9の例（変更3件、除外2件、対象1件）の読みに基づく。閉包と逆参照を含む読みを排除する明記はない。規範文の明記を待つ。
- `scope: changed`は、完全検査した文書数を出力しない（`checkedDocumentCount`は`selected`と`full`だけ）。`MULTI-029-03`が閉包と逆参照を完全検査したことは、他のメンバーの文書の診断の有無で確かめる。
- 閉包で到達した他のメンバーの文書の逆参照（`api::TECH-060`）を対象にしないことは、ユーザー決定に基づく。`check` §3は、直接の逆参照の集合を、引数なしでは「所有する文書と強い関係の閉包の和」と定めており、
  文言どおりに読めば、閉包で到達した`api::TECH-020`を参照する`api::TECH-060`も加わる。単一ワークスペースでは文言どおりである。複合ワークスペースでの「別のワークスペースの無関係な変更を対象へ混ぜない」
  （`check` §6）と「無関係なメンバーを完全検査しない」（複合ワークスペース仕様 §7）の読み方として、閉包で到達した文書の逆参照を除く扱いを固定した。この規則は、
  2026-10-11に`check` §6の複合ワークスペースの節へ明記した（作業ワークスペースの文書の逆参照は従来どおり完全検査の対象のどの文書についても加える）。
- `--full`が、他のメンバーから作業ワークスペースの文書を参照する文書（直接の逆参照）を完全検査するかは固定しない。`MULTI-029-01`／`02`は、そのような文書を置かない。
  `--full`が閉包で到達した他のメンバーの文書（`api::TECH-020`、`platform::REQ-001`）を完全検査の件数へ数えることは、明示対象の`MULTI-004-02`（閉包の`platform::REQ-001`を数える）と同じ扱いで、
  2026-10-11に`check` §6の複合ワークスペースの節へ「引数なし、明示対象、`--full`のどれでも同じ」と明記した。
- 影響候補（`SPEC-IMPACT-OUTDATED-001`）を作業ワークスペースの文書だけに出すことは、2026-10-11に`check` §6の複合ワークスペースの節へ明記した（ユーザー決定）。このfixtureでは固定せず、
  Coreの単体試験で確かめる。`MULTI-029-03`は、
  変更した`web::TECH-030`を参照する`api::TECH-040`を状態`draft`にして、影響候補の対象（`approved`だけ）から外した。
- `changedPathCount`が、作業ワークスペースが所有する変更だけを数えること（他のメンバーの変更を数えない）は固定しない。`MULTI-029-03`は、変更を`web`の1件だけにした。
- コードとテストのパスの変更、リネーム、削除、`--report`、`--all-workspaces`は扱わない。

## 2026-10-11追記: `MULTI-030-01`〜`02`（メンバーの中から実行する`check --full`と`check --all-workspaces`）

### 追加の理由（実装の確認事項C26）

Gitの呼び出しが現在のディレクトリを基準にしていたため、複合ワークスペースのメンバーの中で`check`を実行すると、次の2つが黙って省かれていた（修正はコミット`43bec7ee`、仕様の明記はコミット`57ee44af`）。

- 基準版の仕様文書の一覧が空になり、基準版との比較（削除の検出`SPEC-STATE-TRANSITION-001`、状態遷移、承認済み要求の保護`SPEC-SAFETY-APPROVED-001`）が行われなかった。
- `check --all-workspaces`の全体事前検査の候補が、現在のディレクトリの配下だけになった。メンバーの外の未追跡の`.spec/bitz.yaml`を見落とし、ルートでは`blocked`、`apps/web`では`passed`になった。

既存のfixtureは、メンバーの中の`check`では`MULTI-029-01`〜`03`だけで、基準版との比較を行う変更（削除、`title`の変更）を持たず、`--full`もメンバーの中では`MULTI-029-01`の変更なしの入力だけである。`--all-workspaces`の未登録の判定（`MULTI-006`）はルートで実行する。そこで、メンバーの中から実行する2件を加える。
単一ワークスペースの下位のディレクトリから実行する`SINGLE-158`は、[基準版・状態遷移のレビュー記録](../single/基準版・状態遷移のレビュー記録.md)に記録した。

### 根拠の規範文

- `check` §3・§5: `--full`は作業ワークスペースのすべての仕様文書を完全検査し、基準版との比較（削除の検出、承認済み要求の保護）も行う（既存の`SINGLE-029`が`--full`で削除を固定している）。変更集合と基準版の仕様文書の一覧は、現在のディレクトリによらず、作業ワークスペースのルートを基準に求める。現在のディレクトリがワークスペースのルートの下位でも、ルートで実行した場合と同じ結果にする。
  基準版のIDが現在版にない場合は、管理済みの仕様文書の削除として`failed`とする。
- `check` §6: 複合ワークスペースの単独操作では、作業ワークスペースが所有する変更されたパスだけを出発点にし、基準版との比較（状態遷移、削除の検出、承認済み要求の保護）は作業ワークスペースの文書だけに行う。
  到達した文書の診断は、所有ワークスペースのIDとそのワークスペースのルートからの相対パスで返す。
- 文書・フロントマター・状態仕様 §8・§9: 基準版の`approved`のREQの`title`、規範文、強い関係を、状態を`draft`または`outdated`へ戻さずに変えると`SPEC-SAFETY-APPROVED-001`（`failed`）、基準版のIDが現在版にないと`SPEC-STATE-TRANSITION-001`（`failed`）である。
- 複合ワークスペース仕様 §8: 全体操作は、現在のスナップショットの作業ツリーにある追跡対象またはステージ済みのパスと、Gitが無視しない未追跡のパスから、`.spec/bitz.yaml`の候補を、現在のディレクトリによらずリポジトリ全体から列挙する。
  カタログにない候補があれば`SPEC-MULTI-UNREGISTERED-001`（`blocked`）とし、`workspaces: []`で結果を返す。現在のディレクトリがリポジトリのルートと一致する必要はない（`check` §2）。
- 診断レジストリ: `CHECK-APPROVED-MEANING`、`CHECK-DOCUMENT-DELETED`、`MULTI`の未登録の行（発生元の種類は`file`）。

### 入力と起動

2件とも、ルートワークスペース`platform`と、メンバー`web`（`apps/web`）、`api`（`services/api`）を置く（カタログの列挙順はweb、api）。実行は`apps/web`である。引数は`--full --base HEAD --format json`（`MULTI-030-01`）と`--all-workspaces --base HEAD --format json`（`MULTI-030-02`）にする（監査が、コミット済みのfixtureには明示の`--base`を求める）。

| fixture | 入力 | 準備手順 | 引数 |
|---|---|---|---|
| `MULTI-030-01` | `web`の`approved`のREQ-010（`title: 認証の基準`）とREQ-011（`title: 設定の保護`）。関係はなし | REQ-010の`title`と見出しを`変更後の認証基準`に`update`（状態は`approved`のまま）、REQ-011を`delete`（どちらも作業ツリーの変更） | `check --full` |
| `MULTI-030-02` | `web`のREQ-010だけ（変更なし） | メンバーの外に`tools/x/.spec/bitz.yaml`（`workspace.id: x`）を`create`（未追跡で無視されない） | `check --all-workspaces` |

### 期待値の導き方（Coreの出力を根拠にしない）

`MULTI-030-01`（`scope: full`）。

1. 作業ワークスペースは、`apps/web`の最寄りの設定の`web`（複合ワークスペース仕様 §3の2・3）。結果の`workspace`は`{id: web, path: apps/web}`。
2. 完全検査の対象は、`--full`の規則（`check` §3・§6）で、作業ワークスペースの現在版のすべての仕様文書（`web::REQ-010`の1件。基準版にあったREQ-011は削除されたので現在版にない）と、
   強い関係の閉包・直接の逆参照で到達した他のメンバーの文書である。このfixtureは関係を宣言しないので、閉包にも逆参照にも加わる文書はない。`checkedDocumentCount`は1、
   `checkedStatementCount`は`REQ-010:AC-01`の1件である（`SINGLE-029`が、削除した文書を数えず現在版の文書だけを数えるのと同じ扱い）。`scope: full`は`selection`を持たない。`revision.dirty`は`true`。
3. 診断は、基準版（`HEAD`）の`web`の文書と現在版を文書IDで対応付けて導く。REQ-010は`approved`のまま`title`だけが変わったので`SPEC-SAFETY-APPROVED-001`（`source.key`は`title`）、
   REQ-011は現在版にないので`SPEC-STATE-TRANSITION-001`。`workspaceId`は`web`、`path`は`web`のルートからの相対（`.spec/requirements/REQ-010.md`、`.spec/requirements/REQ-011.md`）。
   順序は`workspaceId`、`path`の辞書順なのでREQ-010が先になる。`failed`／終了コード1。
4. ルートで実行した場合（`--workspace web`）と同じ結果になる。

`MULTI-030-02`（`scope: all-workspaces`）。

1. Gitが認識する`.spec/bitz.yaml`の候補は、追跡対象の3件（ルート、`web`、`api`）と、未追跡で無視されない`tools/x/.spec/bitz.yaml`の4件である。カタログに登録されているのは前の3件で、`tools/x`は未登録である。
   基準版のスナップショットには`tools/x`がなく、未登録は現在のスナップショットの1件だけである。
2. 全体事前検査が非成功なので、メンバーの処理を始めず、`workspaces: []`で`blocked`／終了コード2を返す。診断は`SPEC-MULTI-UNREGISTERED-001`の1件で、未登録の設定はワークスペースではないので
   `workspaceId`は`null`、`path`は`tools/x/.spec/bitz.yaml`である。`revision.dirty`は、未追跡のファイルがあるので`true`（単一ワークスペースの`SINGLE-028`の新規の未追跡ファイルを`dirty: true`とする既存の期待値と同じ扱い）。
3. 候補は現在のディレクトリによらず列挙するので、ルートで実行した場合（`MULTI-006`と同じ形）と同じ結果になる。

監査は、この導出を`repo_root_fixtures.reference_check`として、入力の木構造とGitの状態（常にリポジトリのルートで呼ぶ）から独立に計算し、リテラルの期待値と照合する。さらに、実行するディレクトリを変えた参照計算
（`MULTI-030-01`はルートで`--workspace web`、`MULTI-030-02`はルート、`services/api`、`tools/x`）で、選ぶ作業ワークスペースが同じになることを確かめる（参照計算のGitは
常にリポジトリのルートで呼ぶため、実行場所への依存そのものは修正前のCoreの陰性対照で押さえる）。
原因の構成（基準版の`approved`のREQ 2件のうち、1件は`title`だけの変更、1件は削除、関係なし、変更はインデックスへ入れない、未登録の設定は未追跡でメンバーの外にあり基準版にない）は、
`check_conditions`が入力の木構造とGitの状態から確かめる。

### 監査の検査と回帰試験

`test_conformance_audit.py`の回帰試験は、診断の欠落（`SPEC-SAFETY-APPROVED-001`、`SPEC-STATE-TRANSITION-001`、`SPEC-MULTI-UNREGISTERED-001`のそれぞれ）、状態の改変（`passed`、`failed`、`blocked`の取り違え）、
`workspace`・`workspaceId`・`path`・`scope`の改変、完全検査の件数と`revision.dirty`の改変、`selection`の混入、実行するディレクトリの改変（ルート、別のメンバー、`tools`）、`--full`の削除（`MULTI-030-01`）、`--full`の追加と`--all-workspaces`の削除（`MULTI-030-02`）、準備手順の削除と変更、
入力の改変（基準版の状態、`title`の据置き、規範文の変更、関係の追加、未登録の設定のカタログへの追加とメンバーの配下への移動）、準備手順の結果（変更のステージ、余分な変更、実行するディレクトリの不在）を拒否する。

### 固定しない範囲

- 引数なしの`check`で削除した文書を`selection.targetDocumentCount`に数えるかは規範文が定めておらず（実装の確認事項C28）、このfixtureでは引数なしを使わない。
- `SPEC-SAFETY-APPROVED-001`の`source.key`は、`title`を変えたときの`title`だけを固定する（`SINGLE-031`と同じ）。規範文や強い関係を変えたときの`key`は、規範文が定めないので固定しない（このfixtureは`title`だけを変える）。
- 診断の`summary`は、`SINGLE-029`、`SINGLE-031`、`MULTI-006`と同じ文字列である。`evidence`、`specRefs`、`suggestedAction`は付けない。
- 影響候補、閉包、直接の逆参照、リネーム、ステージ済みの変更、コードとテストのパスは扱わない。`MULTI-030-01`は、他のメンバーの変更を置かず、閉包と逆参照も置かない（`--full`でこれらを完全検査の対象に加える規則は`MULTI-029-01`が固定する）。他のメンバーの変更を置かない（基準版との比較を作業ワークスペースの文書だけに行うことの陰性対照は固定しない）。
- `MULTI-030-02`は、基準版のスナップショットの未登録（初回の複合ワークスペース化、メンバーの削除と移動）を扱わない。未登録の設定がGitに無視されるときや、サブモジュールの内部は扱わない。
- 修正前のCore（コミット`2baa0b79`の`gitutil.py`を、作業ツリーの外のコピーで差し替えて確認した）は、3件とも失敗する（陰性対照）。`MULTI-030-01`は`passed`／終了コード0で診断が返らず、
  `MULTI-030-02`は`passed`／終了コード0でメンバー3件の結果を返す。修正後のCoreは3件とも通る。Coreの出力は期待値を決めた後に、一致を確かめるためだけに使った。
