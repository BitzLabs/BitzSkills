# 適合fixture仕様

## 1. 所有範囲

本書はCore 1.0の適合試験の正本である。fixtureの配置、manifest、共通normalizer、比較規則、
最小matrixを所有する。各fixtureが期待する動作の根拠は当該契約を所有する仕様が定義し、
本書はそれを再定義しない。

Core 1.0の実装受入は、version管理した本matrixの全fixtureが通過することを条件とする。
matrixは最小集合であり、実装は追加fixtureを持ってよいが、本matrixの行を削除・緩和できない。

`MONO-*`の由来は[提案23 §8](../../04.提案資料/23_モノレポ残存P2裁定案.md#8-f-適合fixtureと期待matrix)、
`SINGLE-*`の由来は[提案24](../../04.提案資料/24_Core-1.0実装着手方針.md)である。提案資料は検討履歴であり、
適合条件の正は本書とする。

## 2. 配置

```text
fixtures/conformance/single/<fixture-id>/repo/...
fixtures/conformance/single/<fixture-id>/changes/...
fixtures/conformance/single/<fixture-id>/manifest.json
fixtures/conformance/single/<fixture-id>/expected/<operation>.json
fixtures/conformance/single/<fixture-id>/expected/<operation>.txt
fixtures/conformance/monorepo/<fixture-id>/repo/...
fixtures/conformance/monorepo/<fixture-id>/changes/...
fixtures/conformance/monorepo/<fixture-id>/manifest.json
fixtures/conformance/monorepo/<fixture-id>/expected/<operation>.json
fixtures/conformance/manifest.schema.json
```

`repo/`はbase commitを作る前の入力treeとする。`changes/`は`setup.operations[]`の`source`からだけ参照できる
固定入力であり、実行repositoryへは自動でcopyしない。通常fileのbyte列と実行bit、symlinkのlink文字列を
version管理する。Git履歴とbase commit後の状態はmanifestだけから構築する。
`expected/<operation>.txt`はtext出力を比較するfixtureだけが持つ。
`manifest.schema.json`は全manifestが従うmachine-readable Schemaであり、harnessは実行前にmanifestを検証する。

1つのfixtureは1回のinvocation、1種類の独立原因、1つの期待status、1つの期待exit codeだけを持つ。
並び順や集約を検査するfixtureは、同じ原因を複数位置で発生させてよいが、別の原因を混ぜてはならない。
同じ論点の入力変種、operation変種、成功／非成功変種はfixture ID、入力directory、manifestを分ける。
共通入力を物理的に共有するsymlink、hardlink、親directory参照は使用しない。

fixture IDは`SINGLE-NNN`または`MONO-NNN`をcase familyとし、分割が必要なfamilyは
`SINGLE-NNN-NN`または`MONO-NNN-NN`を使う。計画文書の`SINGLE-001`〜`006`のような範囲表記は、
その範囲に属するsuffix付きfixtureをすべて含む。suffixなしのfamily IDとsuffix付きIDを同時に使ってはならない。

## 3. manifest

```json
{
  "fixtureId": "SINGLE-031",
  "description": "approved REQの意味変更でstatusを戻していない",
  "setup": {
    "git": true,
    "baseCommit": {"message": "base", "paths": ["."]},
    "operations": [
      {
        "op": "update",
        "path": ".spec/REQ/REQ-031_example.md",
        "source": "changes/REQ-031_example.md"
      }
    ]
  },
  "invocation": {
    "runner": "bitz",
    "cwd": ".",
    "argv": ["check", "--base", "HEAD", "--format", "json"],
    "env": {}
  },
  "expect": {
    "status": "failed",
    "exitCode": 1,
    "stdout": "json",
    "resultFile": "expected/check.json",
    "reportFileCount": 0
  }
}
```

| key | 必須 | 意味 |
|---|:--:|---|
| `fixtureId` | Yes | 本matrixのID |
| `description` | Yes | 検査する論点の1行要約 |
| `setup.git` | Yes | Git repositoryを作るか。`false`はGit不在fixture |
| `setup.baseCommit` | No | 基準版commitの作り方。省略時はcommitを作らない |
| `setup.operations` | Yes | base commit後に順番に適用する操作。0件でも配列を置く |
| `invocation.runner` | Yes | `bitz`、`consumer`、`migration`のいずれか |
| `invocation.cwd` | Yes | `repo/`相対の実行directory |
| `invocation.argv` | Yes | 選択したrunnerへ渡す引数列。`bitz`では`bitz`に続く引数。shellを介さない |
| `invocation.env` | Yes | 追加環境変数。0件でもkeyを置く |
| `expect.status` | No | 共通結果を返すinvocationでは必須。引数不正で共通結果を返さない場合だけ省略 |
| `expect.outcome` | No | `consumer`と`migration`だけで必須。`accepted`、`rejected`、`passed`のいずれか |
| `expect.exitCode` | Yes | 期待終了コード |
| `expect.stdout` | Yes | `json`、`text`、`none`のいずれか |
| `expect.resultFile` | No | 期待JSON。`stdout: none`では持たない |
| `expect.textFile` | No | 期待text |
| `expect.reportFileCount` | Yes | 実行後に`.spec/reports/`へ増える件数 |

`runner: bitz`はshellを介さず、repositoryで検査対象の`bitz` entry pointを実行する。
`runner: consumer`と`runner: migration`はCore配布物に含める固定compatibility harnessをshellなしで実行し、
Core共通結果の`status`ではなく`outcome`を返す。この2 runnerのargvと終了コードは各manifestで固定する。

manifestは1つの正確な終了コードとstatusまたはoutcomeを記録する。範囲、選択肢、条件分岐、`元statusと同じ`、
`成功・非成功`のような入力依存表現を書かない。
`setup.baseCommit`を持つfixtureは`--base`をargvへ明示する。Coreはdefault branchとmerge-baseを
推測しないため、fixtureも推測に依存しない。

### 3.1 setupの適用順序

harnessは各fixtureを新しい一時directoryへcopyし、次の順でsetupする。

1. `repo/`の通常fileとdirectoryを一時directoryへcopyする。symlinkはsymlinkとして再作成する。
2. `setup.git: true`なら`git init`し、identity、時刻、default branch名をharnessの固定値にする。
3. `setup.baseCommit`があれば、その`paths[]`だけをstageして1 commitを作る。
4. `setup.operations[]`を配列順に適用する。
5. Git index、working tree、file種別、file byte列がmanifestどおりであることを確認してからinvocationを開始する。

setup用Git値はdefault branch `fixture`、`user.name=Bitz Fixture`、`user.email=fixture@bitz.invalid`、
author／committer日時`2000-01-01T00:00:00Z`、`commit.gpgSign=false`、`core.autocrlf=false`、
`core.fileMode=true`に固定する。host側のglobal／system Git設定を読まず、hookを実行しない。

`setup.git: false`では`baseCommit`、`stage` operation、invocationの`--base`を禁止する。
`setup.git: true`かつ`baseCommit`なし、`operations: []`がunborn repositoryを表す。
`baseCommit`あり、`operations: []`がcleanなcommitted状態を表す。状態名を別fieldで重複指定しない。

### 3.2 operations

各operationは次の閉じた集合とする。全pathはfixtureの一時repository rootからの`/`区切り相対pathであり、
空path、絶対path、`.`、`..` segment、NULを禁止する。`source`はfixture directoryからの相対pathで、
`changes/`配下の通常fileまたはsymlinkだけを指す。operationはshellを介さない。symlinkのsourceと対象は
dereferenceせず、link文字列そのものをcopy・比較する。

| `op` | 必須field | 事前条件 | 結果 |
|---|---|---|---|
| `create` | `path`, `source` | `path`が存在しない | `source`のfile種別、byte列またはlink文字列、実行bitを再現する |
| `update` | `path`, `source` | `path`が通常fileまたはsymlinkとして存在する | `source`のfile種別、byte列またはlink文字列、実行bitで置換する |
| `delete` | `path` | `path`がfile、symlink、またはdirectoryとして存在する | symlinkをdereferenceせず対象treeだけを削除する |
| `rename` | `from`, `to` | `from`が存在し、`to`が存在しない | file、symlink、directory treeを同じfilesystem内で移動する |
| `stage` | `paths` | `setup.git: true` | 列挙pathだけに`git add -A -- <paths...>`相当を適用する |

未知fieldは禁止する。`paths`は1件以上で重複を禁止し、`.`はrepository全体を明示するときだけ許可する。
create、update、renameで親directoryがなければharnessが作成する。delete後に空になった親directoryは残す。
renameとdeleteのGit上の判定はGit自身に委ねるが、期待するindex／working tree状態は後続の`stage`有無で一意に決まる。

### 3.3 実成果物との対応

matrixの各行は同名のfixture directoryを1つ持ち、そのdirectoryは`manifest.json`、`repo/`、必要に応じた
`changes/`、およびmanifestから参照される全`expected/` fileを持たなければならない。matrixだけに存在するID、
manifestだけに存在するID、参照先がないfile、manifestから参照されない期待fileを適合試験開始前のerrorとする。

期待結果のfieldとDiagnosticが後続の規範修正で変わる場合も、選択的期待値を置いてはならない。
当該fixtureを未確定のまま実行対象へ入れず、契約確定と同じ変更で唯一の期待fileを追加する。

## 4. 共通normalizer

比較前に、実際の結果と期待JSONの双方へ同じnormalizerを適用する。除外するのは次だけとする。

- `durationMs`（top-level、`workspaces[]`、`commands[]`のすべて）
- report file名に含まれる生成時刻と連番
- Git commit ID。`revision.base`と`revision.commit`は「40桁の小文字16進」であることだけを検査する
- `core.version`のpatch部
- 実行環境に依存するprocess出力の抜粋

除外fieldをfixtureごとに追加してはならない。上記以外のfield、値、配列順、nullと空配列の区別、
keyの有無はすべて構造比較する。Context Digestは除外せず、期待値との完全一致を要求する。

text比較はUTF-8 byte列の完全一致とする。ただし、実際の出力と期待textの双方について、ASCII正規表現
`\([0-9]+ms\)`に一致するduration tokenだけを`(<duration>ms)`へ置換する。行全体やtoken前後の空白、
status、scope、件数は除外しない。一致するtokenが1行に複数あればすべて置換する。

Context Digest fixtureは、Digest入力のCanonical JSONをUTF-8・BOMなし・末尾改行なしのbyte列として
`expected/context.canonical.json`へ置き、そのbyte列から計算した小文字16進64桁の値を`sha256:`付きで
期待結果へ記録する。harnessはCanonical JSONのbyte一致とDigest文字列の一致を別々に検査する。

## 5. 副作用の検査

全fixtureは実行前後でGit statusとfilesystem manifestを比較する。

- `--report`なしでは、成功・非成功にかかわらずfile生成、既存report更新、cache以外のworkspace書込みを0件とする。
- `--report`指定時は`check`と`verify`だけが指定先へ1件を排他的作成する。
- 引数不正、`context`、`doctor`は`--report`の指定有無にかかわらずreportを作らない。
- Coreは`.spec/`、code、testを変更しない。

## 6. 最小matrix: 単一workspace

### 6.1 導入と設定

| fixture | 主な入力 | operation | status／exit | 必須確認 |
|---|---|---|---|---|
| `SINGLE-001` | 最小`bitz.yaml`だけのworkspace | doctor | passed／0 | `core`、`checks[]`、report 0件 |
| `SINGLE-002` | `.spec/bitz.yaml`不在 | doctor | blocked／2 | `SPEC-DOCTOR-WORKSPACE-001`、最小設定のsuggestedAction |
| `SINGLE-003` | 未知Schema major | check | blocked／2 | `SPEC-CONFIG-SCHEMA-001`、索引を作らない |
| `SINGLE-004-01` | 設定fieldの型不正 | check | error／3 | `SPEC-CONFIG-SCHEMA-001`、`source.key` |
| `SINGLE-004-02` | 設定の必須key欠如 | check | error／3 | `SPEC-CONFIG-SCHEMA-001`、`source.key` |
| `SINGLE-005-01` | 未知標準key | check | passed_with_warnings／0 | `SPEC-CONFIG-UNKNOWN-001`だけ。値を変更しない |
| `SINGLE-005-02` | 予約key `profiles` | check | passed_with_warnings／0 | `SPEC-CONFIG-UNKNOWN-001`だけ。値を変更しない |
| `SINGLE-006-01` | 解決できないcommand実行file | doctor | blocked／2 | `SPEC-DOCTOR-COMMAND-001` |
| `SINGLE-006-02` | 解決できないcommand cwd | doctor | blocked／2 | `SPEC-DOCTOR-COMMAND-001` |

### 6.2 EARS-AIと文書

| fixture | 主な入力 | operation | status／exit | 必須確認 |
|---|---|---|---|---|
| `SINGLE-007` | approved REQのtag順序不正 | check | failed／1 | `EAI-CORE-SYNTAX-001`、行・列 |
| `SINGLE-008` | 同じ違反をdraftで持つ | check | passed_with_warnings／0 | 同codeがwarningへ降格 |
| `SINGLE-009-01` | 桁不足ID | check | failed／1 | `EAI-CORE-ID-001`。本文として見逃さない |
| `SINGLE-009-02` | 未知prefix ID | check | failed／1 | `EAI-CORE-ID-001`。本文として見逃さない |
| `SINGLE-009-03` | 3階層ID | check | failed／1 | `EAI-CORE-ID-001`。本文として見逃さない |
| `SINGLE-010-01` | GFM checkbox | check | passed／0 | 候補Scannerが誤検出しない |
| `SINGLE-010-02` | code span内の角括弧 | check | passed／0 | 候補Scannerが誤検出しない |
| `SINGLE-011` | 規範文ID重複 | check | failed／1 | draftでも`EAI-CORE-ID-002` |
| `SINGLE-012-01` | 未閉鎖tag | check | failed／1 | `EAI-CORE-SYNTAX-004` |
| `SINGLE-012-02` | 未閉鎖code span | check | failed／1 | `EAI-CORE-SYNTAX-005` |
| `SINGLE-012-03` | 句点欠落 | check | failed／1 | `EAI-CORE-SYNTAX-006` |
| `SINGLE-013` | 未知namespaceのextension | check | passed_with_warnings／0 | `EAI-EXT-UNKNOWN-001`、解析を継続 |
| `SINGLE-014` | file名IDとFrontmatter `id`不一致 | check | failed／1 | `SPEC-FILE-NAME-001` |
| `SINGLE-015` | 文書ID重複 | check | failed／1 | `SPEC-ID-DUPLICATE-001`。新IDを提案しない |
| `SINGLE-016` | approved REQに妥当な規範文0件 | check | failed／1 | `SPEC-REQ-STATEMENT-001` |
| `SINGLE-017-01` | H1不一致 | check | failed／1 | `SPEC-STYLE-H1-001` |
| `SINGLE-017-02` | REQ必須H2欠落 | check | failed／1 | `SPEC-STYLE-SECTION-001` |
| `SINGLE-017-03` | ADR内の規範行 | check | failed／1 | `SPEC-STYLE-PLACEMENT-001` |
| `SINGLE-018-01` | H2順序違い | check | passed／0 | style Diagnosticを返さない |
| `SINGLE-018-02` | 空の任意節 | check | passed／0 | style Diagnosticを返さない |
| `SINGLE-018-03` | 疑似節 | check | passed／0 | style Diagnosticを返さない |
| `SINGLE-019` | UTF-8として復号できないfile | check | failed／1 | `SPEC-INPUT-READ-001`、置換文字で継続しない |

### 6.3 関係とtrace

| fixture | 主な入力 | operation | status／exit | 必須確認 |
|---|---|---|---|---|
| `SINGLE-020` | strong target不在 | check | failed／1 | `SPEC-RELATION-MISSING-001`だけ |
| `SINGLE-021` | source／target型不適合 | check | failed／1 | `CTX-RELATION-TYPE-001`。1 edge 1 primary |
| `SINGLE-022-01` | `requires`の禁止循環 | check | failed／1 | `CTX-CYCLE-001` |
| `SINGLE-022-02` | `refines`の禁止循環 | check | failed／1 | `CTX-CYCLE-001` |
| `SINGLE-022-03` | `related`の循環 | check | passed／0 | `CTX-CYCLE-001`を返さない |
| `SINGLE-023` | 旧`refs` | check | failed／1 | `SPEC-RELATION-LEGACY-001`。自動変換しない |
| `SINGLE-024` | approved文書の`implements` path不在 | check | failed／1 | `SPEC-PATH-INVALID-001` |
| `SINGLE-025` | draft文書の未作成予定path | check | passed_with_warnings／0 | 同codeがwarning |
| `SINGLE-026` | 存在しない句への`covers` | check | failed／1 | `SPEC-TEST-COVERAGE-001` |

### 6.4 Git基準版

| fixture | 主な入力 | operation | status／exit | 必須確認 |
|---|---|---|---|---|
| `SINGLE-027` | 禁止状態遷移 | check --base | failed／1 | `SPEC-STATE-TRANSITION-001` |
| `SINGLE-028` | 基準版に存在しない新規文書 | check --base | passed／0 | 現在値の語彙だけを検査 |
| `SINGLE-029` | 管理済みSPECの削除 | check --base | failed／1 | `SPEC-STATE-TRANSITION-001` |
| `SINGLE-030` | pathだけの変更 | check --base | passed／0 | renameとして同一文書 |
| `SINGLE-031` | approved REQの意味変更でstatusを戻さない | check --base | failed／1 | `SPEC-SAFETY-APPROVED-001` |
| `SINGLE-032-01` | `implements`だけの変更 | check --base | passed／0 | 保護対象外 |
| `SINGLE-032-02` | `tests`だけの変更 | check --base | passed／0 | 保護対象外 |
| `SINGLE-032-03` | `related`だけの変更 | check --base | passed／0 | 保護対象外 |
| `SINGLE-032-04` | `x-`拡張fieldだけの変更 | check --base | passed／0 | 保護対象外 |
| `SINGLE-032-05` | 説明文だけの変更 | check --base | passed／0 | 保護対象外 |
| `SINGLE-033` | strong dependencyの変更 | check --base | passed_with_warnings／0 | `SPEC-IMPACT-OUTDATED-001` |
| `SINGLE-034` | 明示TASKの`src/`と`src2/` | check TASK-ID | failed／1 | `SPEC-TASK-BOUNDARY-001`、segment境界 |
| `SINGLE-035-01` | 引数なしcheckでTASKが選ばれる | check | passed／0 | 境界未実施をwarningにしない |
| `SINGLE-035-02` | `check --full`でTASKが選ばれる | check --full | passed／0 | 境界未実施をwarningにしない |
| `SINGLE-036` | 解決できない`--base` | check | 結果なし／4 | stdout結果なし、reportなし |
| `SINGLE-037` | Git不在の引数なしcheck | check | passed_with_warnings／0 | `SPEC-GIT-DEGRADED-001`、失われる保証を明示 |
| `SINGLE-038` | Git不在の明示TASK check | check TASK-ID | blocked／2 | `SPEC-TASK-BOUNDARY-002` |
| `SINGLE-039` | unborn repository | check | passed／0 | 全体check、`revision: null` |
| `SINGLE-040` | 変更集合が空 | check | passed／0 | `selection`3件数、Pre-checkの代用にしない |
| `SINGLE-041` | どの逆索引にも該当しないcode／test変更 | check | passed／0 | Diagnosticなし、件数だけ残す |

### 6.5 contextとDigest

| fixture | 主な入力 | operation | status／exit | 必須確認 |
|---|---|---|---|---|
| `SINGLE-042` | 固定入力の完全解決 | context | passed／0 | 期待Digest値と完全一致 |
| `SINGLE-043-01` | 固定起点を`--detail`付きで解決 | context --detail | passed／0 | `SINGLE-042`とDigest、`resolution`が一致 |
| `SINGLE-043-02` | 固定起点を`--expand`付きで解決 | context --expand | passed／0 | `SINGLE-042`とDigest、`resolution`が一致 |
| `SINGLE-044-01` | 本文の空行数だけを変更 | context | passed／0 | Digestが変化する |
| `SINGLE-044-02` | 表の桁揃えだけを変更 | context | passed／0 | Digestが変化する |
| `SINGLE-045` | `x-`拡張fieldだけを変更 | context | passed／0 | Digestが変化しない |
| `SINGLE-046` | Digest不一致の`--expect-digest` | context | blocked／2 | `CTX-STALE-001` |
| `SINGLE-047` | 解決集合外の`--expand` | context | failed／1 | `CTX-PROJECTION-001`、依存へ追加しない |
| `SINGLE-048-01` | 完全閉包が文書数上限超過 | context | blocked／2 | `CTX-LIMIT-001`、部分Bundleを返さない |
| `SINGLE-048-02` | 完全閉包がbyte上限超過 | context | blocked／2 | `CTX-LIMIT-001`、部分Bundleを返さない |
| `SINGLE-049` | 提示hard limit超過 | context | failed／1 | `CTX-PROJECTION-LIMIT-001` |
| `SINGLE-050` | 起点ID不在 | context | failed／1 | `CTX-ROOT-MISSING-001` |
| `SINGLE-051` | 先行TASKが未done | context --purpose implement | blocked／2 | `CTX-TASK-DEPENDENCY-001` |
| `SINGLE-052-01` | 起点が置換済み | context | blocked／2 | `CTX-STATE-SUPERSEDED-001`、後継へ差替えない |
| `SINGLE-052-02` | 依存先が置換済み | context | blocked／2 | `CTX-STATE-SUPERSEDED-001`、後継へ差替えない |
| `SINGLE-053` | 有効な後継が複数 | context | failed／1 | `CTX-STATE-SUPERSEDED-002` |
| `SINGLE-054` | implement対象MUSTが未addressed | context --purpose implement | passed_with_warnings／0 | `CTX-COVERAGE-TASK-001`、coverage 5区分 |

### 6.6 verify

| fixture | 主な入力 | operation | status／exit | 必須確認 |
|---|---|---|---|---|
| `SINGLE-055` | test成功 | verify | passed／0 | `targetResults[]`、`commands[]`1件、`bindingId`が`<ws>::<name>` |
| `SINGLE-056` | testの非0終了 | verify | failed／1 | `termination: exit`、`exitCode`非0 |
| `SINGLE-057` | command起動不能 | verify | error／3 | `SPEC-VERIFY-COMMAND-001`、`exitCode: null` |
| `SINGLE-058` | signal終了 | verify | error／3 | `termination: signal` |
| `SINGLE-059` | timeout | verify | error／3 | `SPEC-VERIFY-TIMEOUT-001`、実効値は`min(CLI, 設定)` |
| `SINGLE-060` | 対象MUSTが未tested | verify | blocked／2 | `CTX-COVERAGE-TEST-001`、testを開始しない |
| `SINGLE-061` | command名を解決できない | verify | blocked／2 | `SPEC-VERIFY-BLOCKED-001` |
| `SINGLE-062` | 引数なしで対象0件 | verify | blocked／2 | `SPEC-VERIFY-BLOCKED-002`、空CIを成功にしない |
| `SINGLE-063` | 2 targetが同じcommand名を要求 | verify | passed／0 | Digest 2件、command実体1件、test path重複排除 |
| `SINGLE-064` | 非成功targetと通過targetの混在 | verify | blocked／2 | 非成功は`bindingRefs: []`、通過分は実行 |
| `SINGLE-065` | `{tests}`なしcommandと複数test path | verify | passed／0 | argvを1回だけ実行 |
| `SINGLE-066` | 規範文なしTECHの文書単位test | verify | passed／0 | `statements: []`でも`bindingRefs`を持つ |
| `SINGLE-067` | cancelled TASK起点 | verify | blocked／2 | `CTX-STATE-001` |
| `SINGLE-068` | done TASK起点 | verify | passed／0 | 再検証を許可 |
| `SINGLE-069-01` | 成功commandのstdout／stderrが64 KiBを超える | verify | passed／0 | pipeを止めず、抜粋を切詰め表示 |
| `SINGLE-069-02` | 非0終了commandのstdout／stderrが64 KiBを超える | verify | failed／1 | pipeを止めず、抜粋を切詰め表示 |

### 6.7 出力とreport

| fixture | 主な入力 | operation | status／exit | 必須確認 |
|---|---|---|---|---|
| `SINGLE-070-01` | `--report`なしの成功check | check | passed／0 | file生成0件、既存report不変 |
| `SINGLE-070-02` | `--report`なしの失敗check | check | failed／1 | file生成0件、既存report不変 |
| `SINGLE-070-03` | `--report`なしの成功verify | verify | passed／0 | file生成0件、既存report不変 |
| `SINGLE-070-04` | `--report`なしの失敗verify | verify | failed／1 | file生成0件、既存report不変 |
| `SINGLE-071-01` | 明示`--report`付きの成功check | check | passed／0 | 指定先へ1件を排他的作成 |
| `SINGLE-071-02` | 明示`--report`付きの失敗check | check | failed／1 | 指定先へ1件を排他的作成 |
| `SINGLE-071-03` | 明示`--report`付きの成功verify | verify | passed／0 | 指定先へ1件を排他的作成 |
| `SINGLE-071-04` | 明示`--report`付きの失敗verify | verify | failed／1 | 指定先へ1件を排他的作成 |
| `SINGLE-072` | report保存先が書込み不能 | check --report | error／3 | `SPEC-REPORT-WRITE-001`、元結果を端末へ保持 |
| `SINGLE-073-01` | `context`へ`--report` | context | 結果なし／4 | 未知optionとして引数不正 |
| `SINGLE-073-02` | `doctor`へ`--report` | doctor | 結果なし／4 | 未知optionとして引数不正 |
| `SINGLE-074-01` | 排他的optionを同時指定 | check | 結果なし／4 | JSON本体なし、標準エラー1行、report 0件 |
| `SINGLE-074-02` | targetへcode pathを指定 | verify | 結果なし／4 | JSON本体なし、標準エラー1行、report 0件 |
| `SINGLE-074-03` | targetへ構文不正IDを指定 | check | 結果なし／4 | JSON本体なし、標準エラー1行、report 0件 |
| `SINGLE-075-01` | text出力の成功 | check | passed／0 | 成功1行、JSONと同じstatusと件数 |
| `SINGLE-075-02` | text出力の失敗 | check | failed／1 | Diagnostic行形式、JSONと同じstatusと件数 |
| `SINGLE-076` | 端末制御文字を含む失敗Diagnosticのsummaryとpath | check | failed／1 | 無害化して出力 |
| `SINGLE-077` | 同じDiagnostic条件を3か所で発生 | check | failed／1 | workspace、path、line、column、code、specRefsの辞書順 |

### 6.8 上限

| fixture | 主な入力 | operation | status／exit | 必須確認 |
|---|---|---|---|---|
| `SINGLE-078` | `bitz.yaml` 64 KiB超 | check | failed／1 | `SPEC-INPUT-LIMIT-001`、読取りを続けない |
| `SINGLE-079-01` | SPEC Markdown 1 MiB超 | check | failed／1 | `SPEC-INPUT-LIMIT-001` |
| `SINGLE-079-02` | Frontmatter 32 KiB超 | check | failed／1 | `SPEC-INPUT-LIMIT-001` |
| `SINGLE-080-01` | 1文書の規範文と関係配列が`limit` | check | passed／0 | 境界内を誤遮断しない |
| `SINGLE-080-02` | 1文書の規範文が`limit + 1` | check | failed／1 | `SPEC-INPUT-LIMIT-001`だけを返す |
| `SINGLE-080-03` | 1文書の関係配列が`limit + 1` | check | failed／1 | `SPEC-INPUT-LIMIT-001`だけを返す |

### 6.9 Diagnostic registry閉包

| fixture | 主な入力 | operation | status／exit | 必須確認 |
|---|---|---|---|---|
| `SINGLE-081` | `bitz.yaml`先頭の既存BOM | check | passed_with_warnings／0 | `SPEC-INPUT-BOM-001`、BOMを除いて解析継続 |
| `SINGLE-082` | SPEC Markdown先頭の既存BOM | check | passed_with_warnings／0 | `SPEC-INPUT-BOM-001`、Frontmatterを解析継続 |
| `SINGLE-083` | `.spec/`内の未知file | check | passed_with_warnings／0 | `SPEC-WORKSPACE-UNKNOWN-001`、SPECとして読まない |
| `SINGLE-084` | REQにTASK専用`changes` | check | passed_with_warnings／0 | `SPEC-FM-UNAVAILABLE-001`だけ |
| `SINGLE-085` | `x-`で始まらない未知Frontmatter field | check | passed_with_warnings／0 | `SPEC-FM-UNKNOWN-001`だけ |
| `SINGLE-086` | Frontmatter YAML構文不正 | check | failed／1 | `SPEC-FM-SCHEMA-001`だけ |
| `SINGLE-087-01` | Frontmatter custom tag | check | failed／1 | `SPEC-FM-SCHEMA-001`だけ |
| `SINGLE-087-02` | Frontmatter anchor | check | failed／1 | `SPEC-FM-SCHEMA-001`だけ |
| `SINGLE-087-03` | Frontmatter alias | check | failed／1 | `SPEC-FM-SCHEMA-001`だけ |
| `SINGLE-087-04` | Frontmatter merge key | check | failed／1 | `SPEC-FM-SCHEMA-001`だけ |
| `SINGLE-087-05` | Frontmatter重複key | check | failed／1 | `SPEC-FM-SCHEMA-001`だけ |
| `SINGLE-088` | Frontmatter field型不正 | check | failed／1 | `SPEC-FM-SCHEMA-001`だけ |
| `SINGLE-089` | `SHOULD`の理由field欠如 | check | passed_with_warnings／0 | `EAI-CORE-SHOULD-001`だけ |
| `SINGLE-090` | `related` target不在 | check | passed_with_warnings／0 | `SPEC-RELATION-ADVISORY-MISSING-001`だけ |
| `SINGLE-091` | 設定の禁止YAML構文 | check | error／3 | `SPEC-CONFIG-SCHEMA-001`だけ |
| `SINGLE-092` | 設定型不正をdoctorで検査 | doctor | error／3 | `SPEC-CONFIG-SCHEMA-001`だけ。doctor固有config codeなし |
| `SINGLE-093` | 単一workspaceでGit不在 | doctor | passed_with_warnings／0 | `SPEC-DOCTOR-GIT-001`だけ |
| `SINGLE-094` | `.spec/bitz.yaml`不在 | check | blocked／2 | `SPEC-WORKSPACE-MISSING-001`だけ |
| `SINGLE-095` | 未知EARS-AI major | check | blocked／2 | `SPEC-EARS-VERSION-001`だけ |

## 7. 最小matrix: モノレポ連合

| fixture | 主な入力 | operation | status／exit | 必須確認 |
|---|---|---|---|---|
| `MONO-001` | 別workspaceに同じlocal ID | check all | passed／0 | 修飾IDで衝突しない |
| `MONO-002-01` | 横断`refines`と直接coverage | context | passed／0 | 修飾edge、Digest、coverage |
| `MONO-002-02` | 横断`refines`と直接coverage | verify | passed／0 | 修飾edge、Digest、coverage |
| `MONO-003` | 非修飾で別workspaceだけにあるtarget | check all | failed／1 | `SPEC-MONOREPO-REF-001`だけ |
| `MONO-004-01` | context時に存在workspace内のtarget不在 | context | failed／1 | `SPEC-RELATION-MISSING-001`だけ |
| `MONO-004-02` | check時に存在workspace内のtarget不在 | check | failed／1 | `SPEC-RELATION-MISSING-001`だけ |
| `MONO-005` | 未知`--workspace` | check | 結果なし／4 | stdout結果なし、reportなし |
| `MONO-006` | Git既知の未登録設定 | check all | blocked／2 | `workspaces: []`、commandなし |
| `MONO-007-01` | member入れ子 | doctor all | failed／1 | `SPEC-MONOREPO-PATH-001` |
| `MONO-007-02` | memberがsubmodule | doctor all | failed／1 | `SPEC-MONOREPO-PATH-001` |
| `MONO-007-03` | memberが別worktree | doctor all | failed／1 | `SPEC-MONOREPO-PATH-001` |
| `MONO-008` | symlinkで別memberを所有 | check all | failed／1 | ownership code、TASK codeなし |
| `MONO-009` | `src/`と`src2/`のTASK変更 | explicit TASK check | failed／1 | segment境界 |
| `MONO-010` | base/currentでsymlink target変更 | explicit TASK check | failed／1 | 双方の所有判定 |
| `MONO-011` | 1 member文書failed、後続member独立 | check all | failed／1 | 後続member件数を保持 |
| `MONO-012` | invalid文書をstrong依存するtarget | verify all | failed／1 | 依存targetはblocked、独立targetは実行 |
| `MONO-013` | 異なる2 Context、共有binding | verify all | passed／0 | Digest 2件、command 1件 |
| `MONO-014` | command失敗後に独立bindingあり | verify all | failed／1 | 後続bindingも実行 |
| `MONO-015` | 1 memberだけ対象0件 | verify all | passed_with_warnings／0 | member warning、空配列 |
| `MONO-016` | 連合全体で対象0件 | verify all | blocked／2 | 空CIを成功にしない |
| `MONO-017` | ID維持のmember path移動 | check all with base | passed／0 | 同一workspace扱い |
| `MONO-018-01` | memberのworkspace ID変更 | check all with base | failed／1 | 管理済みSPEC削除検査 |
| `MONO-018-02` | member削除 | check all with base | failed／1 | 管理済みSPEC削除検査 |
| `MONO-019` | Git不在 | doctor all | blocked／2 | `SPEC-MONOREPO-GIT-001` |
| `MONO-020-01` | `memberCount = 99` | check all | passed／0 | 境界内を誤遮断しない |
| `MONO-020-02` | `memberCount = 100` | check all | passed／0 | 境界値を誤遮断しない |
| `MONO-020-03` | `specFileCount = 9,999` | check all | passed／0 | 境界内を誤遮断しない |
| `MONO-020-04` | `specFileCount = 10,000` | check all | passed／0 | 境界値を誤遮断しない |
| `MONO-020-05` | `inputBytes = 268,435,455` | check all | passed／0 | 境界内を誤遮断しない |
| `MONO-020-06` | `inputBytes = 268,435,456` | check all | passed／0 | 境界値を誤遮断しない |
| `MONO-020-07` | `statementCount = 99,999` | check all | passed／0 | 境界内を誤遮断しない |
| `MONO-020-08` | `statementCount = 100,000` | check all | passed／0 | 境界値を誤遮断しない |
| `MONO-020-09` | `relationEdgeCount = 999,999` | check all | passed／0 | 境界内を誤遮断しない |
| `MONO-020-10` | `relationEdgeCount = 1,000,000` | check all | passed／0 | 境界値を誤遮断しない |
| `MONO-020-11` | `traceEntryCount = 999,999` | check all | passed／0 | 境界内を誤遮断しない |
| `MONO-020-12` | `traceEntryCount = 1,000,000` | check all | passed／0 | 境界値を誤遮断しない |
| `MONO-020-13` | `commandDefinitionCount = 9,999` | check all | passed／0 | 境界内を誤遮断しない |
| `MONO-020-14` | `commandDefinitionCount = 10,000` | check all | passed／0 | 境界値を誤遮断しない |
| `MONO-020-15` | `verifyBindingCount = 9,999` | verify all | passed／0 | 境界内を誤遮断しない |
| `MONO-020-16` | `verifyBindingCount = 10,000` | verify all | passed／0 | 境界値を誤遮断しない |
| `MONO-021-01` | `memberCount = 101` | check all | blocked／2 | `dimension=memberCount`、`limit=100`、早期停止 |
| `MONO-021-02` | `specFileCount = 10,001` | check all | blocked／2 | `dimension=specFileCount`、`limit=10000`、早期停止 |
| `MONO-021-03` | `inputBytes = 268,435,457` | check all | blocked／2 | `dimension=inputBytes`、`limit=268435456`、早期停止 |
| `MONO-021-04` | `statementCount = 100,001` | check all | blocked／2 | `dimension=statementCount`、`limit=100000`、早期停止 |
| `MONO-021-05` | `relationEdgeCount = 1,000,001` | check all | blocked／2 | `dimension=relationEdgeCount`、`limit=1000000`、早期停止 |
| `MONO-021-06` | `traceEntryCount = 1,000,001` | check all | blocked／2 | `dimension=traceEntryCount`、`limit=1000000`、早期停止 |
| `MONO-021-07` | `commandDefinitionCount = 10,001` | check all | blocked／2 | `dimension=commandDefinitionCount`、`limit=10000`、早期停止 |
| `MONO-021-08` | `verifyBindingCount = 10,001` | verify all | blocked／2 | `dimension=verifyBindingCount`、`limit=10000`、早期停止 |
| `MONO-022-01` | 既定の連合check | check all | passed／0 | report file 0件 |
| `MONO-022-02` | 明示`--report`付き連合check | check all | passed／0 | 指定先へreport 1件 |
| `MONO-022-03` | 既定の連合verify | verify all | passed／0 | report file 0件 |
| `MONO-022-04` | 明示`--report`付き連合verify | verify all | passed／0 | 指定先へreport 1件 |
| `MONO-023-01` | 単一workspace JSON | consumer test | accepted／0 | 単一外形として受理 |
| `MONO-023-02` | 連合JSON | consumer test | accepted／0 | 連合外形として受理 |
| `MONO-023-03` | 単一／連合fieldの混在JSON | consumer test | rejected／1 | 排他的外形として拒否 |
| `MONO-024-01` | 連合形式へのmigration | migration test | passed／0 | 原子的に切り替える |
| `MONO-024-02` | 完全rollback | migration test | passed／0 | 旧形式へ完全に戻る |
| `MONO-024-03` | 部分rollback | migration test | rejected／1 | 部分rollbackを拒否 |

`MONO-012`ではinvalid文書のowner memberを`failed`、それを必要とするtargetを
`SPEC-MONOREPO-DEPENDENCY-001`／`blocked`、独立targetを通過とし、top-levelは最悪値の`failed`に固定する。

## 8. 性能fixture

性能は適合fixtureとは別に、[品質属性と安全境界 §4](../../02.設計書/02_品質属性と安全境界.md#4-性能予算)の
基準fixtureと環境manifestで測定する。測定条件はclean working tree、local SSD、networkなし、
`--report`なし、JSON出力、Core cache無効化、暖機1回後の5回中央値とする。
性能fixtureは合否matrixへ含めず、回帰検査として独立に運用する。

`limit + 1`のhard-limit fixtureは性能SLOの対象ではなく、安全な停止だけを検査する。
