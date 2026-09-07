# Core実行環境・CLI基盤契約

## 1. 対象

本書はCore 1.0の配布物、実行環境、共通CLI argv解析を規定する。各操作が受理するoption、target、排他関係は
各操作仕様を正とし、本書と組み合わせて適用する。判断理由はADR-045へ残すが、実装と適合判定は本書を使用する。

## 2. 実行環境と配布物

- Core 1.0はCPython 3.11以上を対象とする。実装は3.11で利用できる構文と標準library APIだけを使用する。
- PyPI distribution名、import package名、CLI実行体名はすべて`bitz`とする。
- Agent Plugins経路のplugin IDは`bitz-core`と`bitz-sdd`とし、`bitz-core`がCLIを同梱または参照する。
  どの配布経路でも利用者が起動するcommandは`bitz`である。
- runtime依存はPython標準libraryとYAML解析library 1つだけに限る。YAML解析libraryはlock fileでexact versionへ固定し、
  公開物をsource commitとbuild手順へ対応付ける。Coreは通常操作中に依存を取得または更新しない。
- 下限version、配布物名、runtime依存の追加・削除はCore minor以上の変更とし、patch releaseでは変更しない。

## 3. YAML loader

YAML解析libraryはYAML 1.2を解釈できるsafe/read-only loaderとして使用し、任意objectの構築やcode実行を許可しない。
Coreは値をSchemaへ渡す前に、custom tag、anchor、alias、merge key、複雑key、複数document、重複mapping keyを
明示的に拒否する。timestamp、`yes`／`no`、先頭`0`をlibrary既定の日時、boolean、8進数へ暗黙変換しない。
受理するscalarと入力別構造はworkspace・設定仕様とFrontmatter仕様を正とし、libraryの既定挙動を仕様の代わりにしない。

## 4. Git

Gitは2.30以上を対象とし、CLI実行体をargvで直接起動する。shell、libgit2 binding、Git機能の独自再実装を使用しない。
下限未満、PATHから解決不能、または実行不能なGitはGit不在として共通の縮退契約を適用する。連合操作では
`SPEC-MONOREPO-GIT-001`／blockedとする。Coreの通常操作はnetworkへ接続せず、Gitにもnetwork操作を要求しない。

## 5. 共通CLI argv解析

CLIはoperation固有処理、workspace探索、file読取りより前にargvを検査する。公開構文に記載したlong optionだけを受理し、
未知option、option値不足、許可されない値、排他違反は終了コード4とする。option名と値は別argv要素で渡し、
`--format=json`のような`--name=value`形式、短縮option、暗黙の環境変数または設定fileによるCLI option追加は受理しない。

値を1つ取るoptionと値を取らないflagは1 invocationに各1回までとし、同じ値でも重複指定は終了コード4とする。
反復可能なのは、公開構文が`...`を付けた`context --expand`と`doctor --require-capability`だけである。
反復可能optionの同じ値は入力順によらず1件へ重複排除し、操作仕様のsort規則を適用する。

空stringの位置引数と空stringのoption値は省略として扱わず終了コード4とする。空白だけの値も、該当するID、path、enum、
versionまたはrangeの構文に一致しないため終了コード4とする。`context`は1件以上の起点を必須とする。`check`と`verify`の
位置引数0件は各仕様が定める引数なし操作であり、空string 1件とは異なる。

`verify --timeout`はASCII数字だけの十進表記で、先頭`0`を含まない`1`〜`3600`を受理する。符号、小数、指数表記、
桁区切り、前後空白は終了コード4とする。

## 6. targetとworkspaceの不存在

targetの字句または種別が操作の公開構文に適合しない場合は終了コード4とする。構文上妥当な文書ID、statement ID、
または許可されたSPEC pathがcatalogに存在しない場合は操作を開始し、`CTX-ROOT-MISSING-001`／failedを返す。
複数targetの一部だけが不在でも、操作仕様の継続単位に従う。checkは既知targetの検査を続け、verifyは独立した既知targetの
結果を保持する。contextは全起点を1つのBundleとして扱うためfailedとし、既知起点だけのBundleをcompleteとして返さない。

`--workspace`はCLIの解決基準そのものなので、構文上妥当でもcatalogに存在しない値は終了コード4とし、操作結果を作らない。
`context --expand`はtargetではなくprojection指定であり、完全解決集合外なら`CTX-PROJECTION-001`／failedとする。

## 7. report flag

`--report`は値を取らないboolean flagで、`check`と`verify`だけが受理する。任意の保存pathをCLIから指定する機能は
Core 1.0に含めず、`--report=<path>`は未知option形式として終了コード4とする。保存directoryとfile名、排他的作成、
失敗処理は結果・Diagnostic・終了コード仕様のreport契約に従う。`--format json`は`--report`を含意せず、両者は排他でない。
