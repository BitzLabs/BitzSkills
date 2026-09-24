# Frontmatter境界fixture review

2026-09-17。SINGLE-114〜120の24件を追加する。最初の20件の後、118-02、118-03、120-01、120-02の4件を追補した。
根拠は[Diagnostic registry](../../../docs/03.詳細設計/00_共通契約/05_Diagnostic-registry.md)、
[文書・Frontmatter仕様](../../../docs/03.詳細設計/02_SPECモデル/02_文書・Frontmatter・状態仕様.md)、
[適合fixture仕様](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md)の各matrix IDと
`frontmatter.schema.json`である。

| ID | 唯一の条件 | status／終了コード | 検査文書／句 | Diagnostic key |
|---|---|---|---|---|
| SINGLE-114 | REQの`tests` object配列 | passed／0 | 1／1 | — |
| SINGLE-115-01 | 最小REQ | passed／0 | 1／1 | — |
| SINGLE-115-02 | 最小TECH | passed／0 | 1／0 | — |
| SINGLE-115-03 | 最小ADR | passed／0 | 1／0 | — |
| SINGLE-115-04 | `changes`省略の最小TASK | passed／0 | 1／0 | — |
| SINGLE-116-01 | titleが120 code point | passed／0 | 1／1 | — |
| SINGLE-116-02 | titleが121 code point | failed／1 | 0／0 | `title` |
| SINGLE-116-03 | titleが空文字列 | failed／1 | 0／0 | `title` |
| SINGLE-116-04 | titleが空白だけ | failed／1 | 0／0 | `title` |
| SINGLE-116-05 | titleが改行を含む | failed／1 | 0／0 | `title` |
| SINGLE-117-01 | title欠落（`SPEC-FM-REQUIRED-001`） | failed／1 | 0／0 | `title` |
| SINGLE-117-02 | titleがnull | failed／1 | 0／0 | `title` |
| SINGLE-117-03 | `tests[0].covers`が空配列 | failed／1 | 0／0 | `tests[0].covers` |
| SINGLE-118-01 | `relations.related`の値重複 | failed／1 | 0／0 | `relations.related` |
| SINGLE-118-02 | `covers`順だけが異なる2件のtest要素 | failed／1 | 0／0 | `tests` |
| SINGLE-118-03 | 同じpathでcommandまたはcoversが異なる3件のtest要素 | passed／0 | 1／2 | — |
| SINGLE-119-01 | `relations`内の未知key | failed／1 | 0／0 | `relations.future` |
| SINGLE-119-02 | `tests[]`内の未知key | failed／1 | 0／0 | `tests[0].future` |
| SINGLE-119-03 | 最上位未知field（`SPEC-FM-UNKNOWN-001`） | passed_with_warnings／0 | 1／1 | `future` |
| SINGLE-119-04 | `x-reviewed`拡張field | passed／0 | 1／1 | — |
| SINGLE-120-01 | TASK `changes: []`、変更差分なし（明示TASK check） | passed／0 | 1／0 | — |
| SINGLE-120-02 | `changes`省略TASK、`src/app.py`に未stage差分（`SPEC-TASK-BOUNDARY-001`） | failed／1 | 1／0 | なし（source pathは`src/app.py`） |
| SINGLE-120-03 | REQに正しい型の`changes`（`SPEC-FM-UNAVAILABLE-001`） | passed_with_warnings／0 | 1／1 | `changes` |
| SINGLE-120-04 | REQに型不正の`changes` | failed／1 | 0／0 | `changes` |

明記のないfailedは`SPEC-FM-SCHEMA-001`だけを持つ。検査句はREQの規範文数であり、118-02／03だけ2件、他のREQは1件、TECH、ADR、TASKは0件である。
Frontmatterを拒否したcaseだけ文書をskipし、件数を0にする。120-02はFrontmatterを受理したうえでの境界違反なので、文書1件を数える。

共通入力は最小設定と対象文書1件である。各fieldをJSON構文のYAML flow valueとして1行ずつ書く。
監査はその行を`json.loads`で独立にdecodeし、期待fieldと一致すること、
`frontmatter.schema.json`の種別definitionの合否がFrontmatter拒否の期待と一致することを確認する。
H1は有効なtitleと一致させ、Frontmatter拒否時は固定titleを使う。title長以外の独立原因を混ぜないためである。
`tests`を持つ場合だけtest fileと`default` command bindingを置く。test fileは実行されると例外を送出し、
checkがtestを実行しないことを入力側でも示す。

実行は`check --full --base HEAD --format json`とし、入力をbase commitへ入れてGit縮退や変更保護を混ぜない。
120-01／02だけは`check TASK-001 --base HEAD --format json`で明示TASK checkを行う。両者とも`src/app.py`をbaseへ入れ、
120-02だけがsetup operationで作業treeの同fileを更新する。stageもcommitもしない。監査はHEADとindexのblobがbase入力、
作業treeが変更適用後と一致することをbyteで確認する。境界違反の診断文面とsourceの形は`SINGLE-034`に揃える。
他のDiagnosticの`summary`は利用者へ示す文面であり、manifestの`description`（検査の論点）とは別に持つ。
同じ条件の既存fixtureがあれば文面を揃える（119-03は`SINGLE-085`、120-03は`SINGLE-084`）。

`tests`の重複判定は、仕様どおり`(path, commandの有無と値, covers集合)`のkey tupleで独立に計算する。
JSON Schemaの`uniqueItems`は配列順を区別するため、118-02を検出できない。監査はSchema違反またはkey tuple重複を
「Frontmatter拒否」とし、期待と一致することを確認する。118-02の2件目の規範文`AC-02`は、理由なしSHOULDの
warningを混ぜないようMUSTにする。118-03は`default`に加えて`other` command定義を設定へ置く。
副作用は読取り専用とし、before／afterを同一に固定する。隔離repositoryを2回setupし、固定snapshotと相互の一致を検査する。
回帰試験では、status、件数、診断codeの改変、二重診断、診断の削除、cache書込みの許容、
121 code point titleの境界内への修復をいずれも拒否する。
追補分では、118-02の受理への改変とcovers順の修復、118-03の件数改変、120-01の`--full`への置換、
120-02の文書件数0への改変、診断sourceへのkey付加、未stage差分の消去とstageの追加も拒否する。

検証用YAML loaderやCoreは実装しない。実YAML解析と拒否順序はStep 2のGate Bで受け入れる。
