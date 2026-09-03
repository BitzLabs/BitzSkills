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
fixtures/conformance/single/<fixture-id>/manifest.json
fixtures/conformance/single/<fixture-id>/expected/<operation>.json
fixtures/conformance/single/<fixture-id>/expected/<operation>.txt
fixtures/conformance/monorepo/<fixture-id>/repo/...
fixtures/conformance/monorepo/<fixture-id>/manifest.json
fixtures/conformance/monorepo/<fixture-id>/expected/<operation>.json
```

`repo/`は入力treeとし、必要な場合だけGit履歴の作り方をmanifestで指示する。
`expected/<operation>.txt`はtext出力を比較するfixtureだけが持つ。

1つのfixtureへ複数の独立原因を混ぜない。同じ論点の変種は入力directoryとmanifestを分ける。

## 3. manifest

```json
{
  "fixtureId": "SINGLE-031",
  "description": "approved REQの意味変更でstatusを戻していない",
  "setup": {
    "git": true,
    "baseCommit": {"message": "base", "paths": ["."]},
    "currentState": "worktree"
  },
  "invocation": {
    "cwd": ".",
    "argv": ["check", "--base", "HEAD", "--format", "json"],
    "env": {}
  },
  "expect": {
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
| `setup.currentState` | Yes | `committed`、`staged`、`worktree`、`unborn`のいずれか |
| `invocation.cwd` | Yes | `repo/`相対の実行directory |
| `invocation.argv` | Yes | `bitz`に続く引数列。shellを介さない |
| `invocation.env` | Yes | 追加環境変数。0件でもkeyを置く |
| `expect.exitCode` | Yes | 期待終了コード |
| `expect.stdout` | Yes | `json`、`text`、`none`のいずれか |
| `expect.resultFile` | No | 期待JSON。`stdout: none`では持たない |
| `expect.textFile` | No | 期待text |
| `expect.reportFileCount` | Yes | 実行後に`.spec/reports/`へ増える件数 |

manifestは1つの正確な終了コードとstatusを記録する。範囲、選択肢、条件分岐を書かない。
`setup.baseCommit`を持つfixtureは`--base`をargvへ明示する。Coreはdefault branchとmerge-baseを
推測しないため、fixtureも推測に依存しない。

## 4. 共通normalizer

比較前に、実際の結果と期待JSONの双方へ同じnormalizerを適用する。除外するのは次だけとする。

- `durationMs`（top-level、`workspaces[]`、`commands[]`のすべて）
- report file名に含まれる生成時刻と連番
- Git commit ID。`revision.base`と`revision.commit`は「40桁の小文字16進」であることだけを検査する
- `core.version`のpatch部
- 実行環境に依存するprocess出力の抜粋

除外fieldをfixtureごとに追加してはならない。上記以外のfield、値、配列順、nullと空配列の区別、
keyの有無はすべて構造比較する。Context Digestは除外せず、期待値との完全一致を要求する。

text比較は行単位の完全一致とし、所要時間を含む行だけを除外する。

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
| `SINGLE-004` | 設定の型不正・必須key欠如 | check | error／3 | `SPEC-CONFIG-SCHEMA-001`、`source.key` |
| `SINGLE-005` | 未知標準keyと`profiles` | check | passed_with_warnings／0 | warningのみ、値を変更しない |
| `SINGLE-006` | 解決できないcommand実行fileとcwd | doctor | blocked／2 | `SPEC-DOCTOR-COMMAND-001` |

### 6.2 EARS-AIと文書

| fixture | 主な入力 | operation | status／exit | 必須確認 |
|---|---|---|---|---|
| `SINGLE-007` | approved REQのtag順序不正 | check | failed／1 | `EAI-CORE-SYNTAX-001`、行・列 |
| `SINGLE-008` | 同じ違反をdraftで持つ | check | passed_with_warnings／0 | 同codeがwarningへ降格 |
| `SINGLE-009` | 桁不足・未知prefix・3階層ID | check | failed／1 | `EAI-CORE-ID-001`。本文として見逃さない |
| `SINGLE-010` | GFM checkboxとcode span内の角括弧 | check | passed／0 | 候補Scannerが誤検出しない |
| `SINGLE-011` | 規範文ID重複 | check | failed／1 | draftでも`EAI-CORE-ID-002` |
| `SINGLE-012` | 未閉鎖tag、未閉鎖code span、句点欠落 | check | failed／1 | `EAI-CORE-SYNTAX-004`〜`006` |
| `SINGLE-013` | 未知namespaceのextension | check | passed_with_warnings／0 | `EAI-EXT-UNKNOWN-001`、解析を継続 |
| `SINGLE-014` | file名IDとFrontmatter `id`不一致 | check | failed／1 | `SPEC-FILE-NAME-001` |
| `SINGLE-015` | 文書ID重複 | check | failed／1 | `SPEC-ID-DUPLICATE-001`。新IDを提案しない |
| `SINGLE-016` | approved REQに妥当な規範文0件 | check | failed／1 | `SPEC-REQ-STATEMENT-001` |
| `SINGLE-017` | H1不一致、REQ必須H2欠落、ADR内の規範行 | check | failed／1 | `SPEC-STYLE-H1-001`／`SECTION-001`／`PLACEMENT-001` |
| `SINGLE-018` | H2順序違い、空の任意節、疑似節 | check | passed／0 | style Diagnosticを返さない |
| `SINGLE-019` | UTF-8として復号できないfile | check | failed／1 | `SPEC-INPUT-READ-001`、置換文字で継続しない |

### 6.3 関係とtrace

| fixture | 主な入力 | operation | status／exit | 必須確認 |
|---|---|---|---|---|
| `SINGLE-020` | strong target不在 | check | failed／1 | `SPEC-RELATION-MISSING-001`だけ |
| `SINGLE-021` | source／target型不適合 | check | failed／1 | `CTX-RELATION-TYPE-001`。1 edge 1 primary |
| `SINGLE-022` | `requires`／`refines`の禁止循環 | check | failed／1 | `CTX-CYCLE-001`。`related`循環は許可 |
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
| `SINGLE-032` | `implements`、`tests`、`related`、`x-`、説明文だけの変更 | check --base | passed／0 | 保護対象外 |
| `SINGLE-033` | strong dependencyの変更 | check --base | passed_with_warnings／0 | `SPEC-IMPACT-OUTDATED-001` |
| `SINGLE-034` | 明示TASKの`src/`と`src2/` | check TASK-ID | failed／1 | `SPEC-TASK-BOUNDARY-001`、segment境界 |
| `SINGLE-035` | 引数なし・`--full`でTASKが選ばれる | check | passed／0 | 境界未実施をwarningにしない |
| `SINGLE-036` | 解決できない`--base` | check | 結果なし／4 | stdout結果なし、reportなし |
| `SINGLE-037` | Git不在の引数なしcheck | check | passed_with_warnings／0 | 全体checkへ縮退、失われる保証を明示 |
| `SINGLE-038` | Git不在の明示TASK check | check TASK-ID | blocked／2 | `SPEC-TASK-BOUNDARY-002` |
| `SINGLE-039` | unborn repository | check | passed／0 | 全体check、`revision: null` |
| `SINGLE-040` | 変更集合が空 | check | passed／0 | `selection`3件数、Pre-checkの代用にしない |
| `SINGLE-041` | どの逆索引にも該当しないcode／test変更 | check | passed／0 | Diagnosticなし、件数だけ残す |

### 6.5 contextとDigest

| fixture | 主な入力 | operation | status／exit | 必須確認 |
|---|---|---|---|---|
| `SINGLE-042` | 固定入力の完全解決 | context | passed／0 | 期待Digest値と完全一致 |
| `SINGLE-043` | 同じ起点で`--detail`と`--expand`を変える | context | passed／0 | Digest不変、`resolution`不変 |
| `SINGLE-044` | 本文の空行数と表の桁揃えだけを変更 | context | passed／0 | Digestが変化する |
| `SINGLE-045` | `x-`拡張fieldだけを変更 | context | passed／0 | Digestが変化しない |
| `SINGLE-046` | Digest不一致の`--expect-digest` | context | blocked／2 | `CTX-STALE-001` |
| `SINGLE-047` | 解決集合外の`--expand` | context | failed／1 | `CTX-PROJECTION-001`、依存へ追加しない |
| `SINGLE-048` | 完全閉包が文書数・byte上限超過 | context | blocked／2 | `CTX-LIMIT-001`、部分Bundleを返さない |
| `SINGLE-049` | 提示hard limit超過 | context | failed／1 | `CTX-PROJECTION-LIMIT-001` |
| `SINGLE-050` | 起点ID不在 | context | failed／1 | `CTX-ROOT-MISSING-001` |
| `SINGLE-051` | 先行TASKが未done | context --purpose implement | blocked／2 | `CTX-TASK-DEPENDENCY-001` |
| `SINGLE-052` | 起点または依存先が置換済み | context | blocked／2 | `CTX-STATE-SUPERSEDED-001`、後継へ差替えない |
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
| `SINGLE-069` | stdout／stderrが64 KiBを超える | verify | 元statusと同じ | pipeを止めず、抜粋を切詰め表示 |

### 6.7 出力とreport

| fixture | 主な入力 | operation | status／exit | 必須確認 |
|---|---|---|---|---|
| `SINGLE-070` | `--report`なしの成功・非成功 | check、verify | 元statusと同じ | file生成0件、既存report不変 |
| `SINGLE-071` | 明示`--report` | check、verify | 元statusと同じ | 指定先へ1件を排他的作成 |
| `SINGLE-072` | report保存先が書込み不能 | check --report | error／3 | `SPEC-REPORT-WRITE-001`、元結果を端末へ保持 |
| `SINGLE-073` | `context`、`doctor`へ`--report` | context、doctor | 結果なし／4 | 未知optionとして引数不正 |
| `SINGLE-074` | 排他違反、code path指定、不正ID | check、verify | 結果なし／4 | JSON本体なし、標準エラー1行、report 0件 |
| `SINGLE-075` | text出力の成功と非成功 | check | 元statusと同じ | 成功1行、Diagnostic行形式、JSONと同じstatusと件数 |
| `SINGLE-076` | 端末制御文字を含むsummaryとpath | check | 元statusと同じ | 無害化して出力 |
| `SINGLE-077` | Diagnostic 3件以上の並び | check | failed／1 | workspace、path、line、column、code、specRefsの辞書順 |

### 6.8 上限

| fixture | 主な入力 | operation | status／exit | 必須確認 |
|---|---|---|---|---|
| `SINGLE-078` | `bitz.yaml` 64 KiB超 | check | error／3 | 読取りを続けない |
| `SINGLE-079` | SPEC Markdown 1 MiB超、Frontmatter 32 KiB超 | check | failed／1 | 入力不適合 |
| `SINGLE-080` | 1文書の規範文と関係配列の`limit`と`limit + 1` | check | passed／0、failed／1 | 境界内を誤遮断しない |

## 7. 最小matrix: モノレポ連合

| fixture | 主な入力 | operation | status／exit | 必須確認 |
|---|---|---|---|---|
| `MONO-001` | 別workspaceに同じlocal ID | check all | passed／0 | 修飾IDで衝突しない |
| `MONO-002` | 横断`refines`と直接coverage | context、verify | passed／0 | 修飾edge、Digest、coverage |
| `MONO-003` | 非修飾で別workspaceだけにあるtarget | check all | failed／1 | `SPEC-MONOREPO-REF-001`だけ |
| `MONO-004` | 存在workspace内のtarget不在 | context、check | failed／1 | `SPEC-RELATION-MISSING-001`だけ |
| `MONO-005` | 未知`--workspace` | check | 結果なし／4 | stdout結果なし、reportなし |
| `MONO-006` | Git既知の未登録設定 | check all | blocked／2 | `workspaces: []`、commandなし |
| `MONO-007` | member入れ子、submodule、別worktree | doctor all | failed／1 | `SPEC-MONOREPO-PATH-001` |
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
| `MONO-018` | ID変更またはmember削除 | check all with base | failed／1 | 管理済みSPEC削除検査 |
| `MONO-019` | Git不在 | doctor all | blocked／2 | `SPEC-MONOREPO-GIT-001` |
| `MONO-020` | 各resourceの`limit - 1`／`limit` | check／verify all | passed／0 | 境界内を誤遮断しない |
| `MONO-021` | 各resourceの`limit + 1` | check／verify all | blocked／2 | dimension、limit、早期停止 |
| `MONO-022` | default実行と明示`--report` | check／verify all | 元statusと同じ | default 0 file、明示時だけ1 file |
| `MONO-023` | 単一／連合／混在JSON | consumer test | accept／reject | 排他的外形とdual-read |
| `MONO-024` | migrationと完全／部分rollback | migration test | pass／reject | 原子的切替、部分rollback拒否 |

`MONO-012`ではinvalid文書のowner memberを`failed`、それを必要とするtargetを
`SPEC-MONOREPO-DEPENDENCY-001`／`blocked`、独立targetを通過とし、top-levelは最悪値の`failed`に固定する。

## 8. 性能fixture

性能は適合fixtureとは別に、[品質属性と安全境界 §4](../../02.設計書/02_品質属性と安全境界.md#4-性能予算)の
基準fixtureと環境manifestで測定する。測定条件はclean working tree、local SSD、networkなし、
`--report`なし、JSON出力、Core cache無効化、暖機1回後の5回中央値とする。
性能fixtureは合否matrixへ含めず、回帰検査として独立に運用する。

`limit + 1`のhard-limit fixtureは性能SLOの対象ではなく、安全な停止だけを検査する。
