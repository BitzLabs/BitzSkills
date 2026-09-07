# Diagnostic registry

## 1. 所有範囲

本書はCore 1.0が操作結果へ返すDiagnostic条件の唯一のregistryである。各操作仕様とSPECモデル仕様は、
条件を検出する処理と補足情報を定義するが、`conditionId`、code、severity、`resultStatus`、source kind、
継続単位、primary優先順位を再定義しない。表にない条件から公開Diagnosticを生成してはならない。

CLI引数不正の終了コード4はCore操作を開始せず、Diagnosticを返さないため本registryの対象外とする。
doctorの`checks[].status`は検査単位の状態であり、Diagnostic `resultStatus`とは別である。
operationsの`parse`は、SPEC本文を解析する`context`、`check`、`verify`を表す。

## 2. fieldと判定規則

| field | 意味 |
|---|---|
| `conditionId` | 条件を識別する永続ID。名称変更や再利用を禁止する |
| operations | 条件を返し得る操作。`all`は4操作、`parse`は入力を解析する操作 |
| code | 公開Diagnostic code |
| severity | `info`、`warning`、`error` |
| status | Diagnosticの`resultStatus` |
| source | `file`、`environment`、`invocation` |
| continuation | Diagnosticを確定した後に処理を継続できる最小単位 |
| priority | 同一原因に複数条件が成立した場合のprimary選択順。小さい値を優先する |

continuationは次の閉じた語彙を使う。

| 値 | 意味 |
|---|---|
| `stop-operation` | 操作全体を停止する |
| `stop-federation` | global preflightで停止し、member処理を開始しない |
| `skip-workspace` | 当該workspaceの依存処理を省略し、独立workspaceを継続する |
| `skip-document` | 当該文書の後続処理を省略し、独立文書を継続する |
| `skip-edge` | 当該relation edgeの後続解決だけを省略する |
| `skip-target` | 当該targetのbindingを実行せず、独立targetを継続する |
| `skip-binding` | 当該bindingだけを実行せず、独立bindingを継続する |
| `skip-check` | 当該doctor checkだけを省略し、独立checkを継続する |
| `continue` | 同じ処理単位の検査を継続する |

1つのraw原因から同義Diagnosticを複数生成しない。同じ処理単位で複数の条件候補が同じraw原因に対応する場合、
priorityが最小の行だけをprimaryとして返す。同じpriorityの候補が残る場合は本registryの上から先にある行を返す。
独立したraw原因はそれぞれprimaryを持ち、結果内の表示順は共通結果契約のsort規則に従う。

## 3. 入力、設定、Frontmatter

| conditionId | operations | code | severity | status | source | continuation | priority | 条件 |
|---|---|---|---|---|---|---|---:|---|
| `WORKSPACE-CONFIG-MISSING` | context, check, verify | `SPEC-WORKSPACE-MISSING-001` | error | blocked | environment | `stop-operation` | 90 | 探索範囲に`.spec/bitz.yaml`がない |
| `INPUT-IO-CONFIG` | all | `SPEC-INPUT-READ-001` | error | error | file | `stop-operation` | 100 | 設定fileの権限、I/O、読取り中消失 |
| `INPUT-UTF8-CONFIG` | all | `SPEC-INPUT-READ-001` | error | failed | file | `stop-operation` | 110 | 設定fileをUTF-8として復号不能 |
| `INPUT-IO-SPEC` | parse | `SPEC-INPUT-READ-001` | error | error | file | `skip-document` | 100 | SPEC Markdownの権限、I/O、読取り中消失 |
| `INPUT-UTF8-SPEC` | parse | `SPEC-INPUT-READ-001` | error | failed | file | `skip-document` | 110 | SPEC MarkdownをUTF-8として復号不能 |
| `INPUT-BOM-CONFIG` | all | `SPEC-INPUT-BOM-001` | warning | passed_with_warnings | file | `continue` | 120 | 設定file先頭に既存BOM |
| `INPUT-BOM-SPEC` | parse | `SPEC-INPUT-BOM-001` | warning | passed_with_warnings | file | `continue` | 120 | SPEC Markdown先頭に既存BOM |
| `INPUT-LIMIT-CONFIG` | all | `SPEC-INPUT-LIMIT-001` | error | failed | file | `stop-operation` | 130 | `bitz.yaml`が64 KiB超過 |
| `INPUT-LIMIT-SPEC` | parse | `SPEC-INPUT-LIMIT-001` | error | failed | file | `skip-document` | 130 | SPEC Markdownが1 MiB超過 |
| `INPUT-LIMIT-FRONTMATTER` | parse | `SPEC-INPUT-LIMIT-001` | error | failed | file | `skip-document` | 130 | Frontmatterが32 KiB超過 |
| `INPUT-LIMIT-SPEC-COUNT` | parse | `SPEC-INPUT-LIMIT-001` | error | failed | file | `stop-operation` | 130 | 単一workspaceのSPEC file数が10,000超過 |
| `INPUT-LIMIT-STATEMENT-COUNT` | parse | `SPEC-INPUT-LIMIT-001` | error | failed | file | `skip-document` | 130 | 1文書の規範文数が1,000超過 |
| `INPUT-LIMIT-ARRAY-COUNT` | parse | `SPEC-INPUT-LIMIT-001` | error | failed | file | `skip-document` | 130 | 1文書の関係・path配列の項目数が1,000超過 |
| `CONFIG-YAML-SYNTAX` | all | `SPEC-CONFIG-SCHEMA-001` | error | error | file | `stop-operation` | 140 | 設定YAMLの構文不正 |
| `CONFIG-YAML-FORBIDDEN` | all | `SPEC-CONFIG-SCHEMA-001` | error | error | file | `stop-operation` | 141 | custom tag、anchor、alias、merge key、重複key |
| `CONFIG-FIELD-TYPE` | all | `SPEC-CONFIG-SCHEMA-001` | error | error | file | `stop-operation` | 142 | 設定fieldの型または値域不正 |
| `CONFIG-FIELD-REQUIRED` | all | `SPEC-CONFIG-SCHEMA-001` | error | error | file | `stop-operation` | 143 | 設定の必須field欠如 |
| `CONFIG-SCHEMA-MAJOR` | all | `SPEC-CONFIG-SCHEMA-001` | error | blocked | file | `stop-operation` | 144 | 未対応Schema major |
| `EARS-SCHEMA-MAJOR` | context, check, verify | `SPEC-EARS-VERSION-001` | error | blocked | file | `stop-operation` | 145 | 未対応EARS-AI major |
| `CONFIG-SCHEMA-MINOR-NEWER` | all | `SPEC-CONFIG-UNKNOWN-001` | warning | passed_with_warnings | file | `continue` | 149 | 同じmajorの新しいSchema minor |
| `CONFIG-KEY-PROFILES` | all | `SPEC-CONFIG-UNKNOWN-001` | warning | passed_with_warnings | file | `continue` | 150 | 予約key `profiles` |
| `CONFIG-KEY-UNKNOWN` | all | `SPEC-CONFIG-UNKNOWN-001` | warning | passed_with_warnings | file | `continue` | 151 | 同一majorの未知標準key |
| `WORKSPACE-ENTRY-UNKNOWN` | check, doctor | `SPEC-WORKSPACE-UNKNOWN-001` | warning | passed_with_warnings | file | `continue` | 160 | `.spec/`内の未知fileまたはdirectory |
| `FM-YAML-SYNTAX` | parse | `SPEC-FM-SCHEMA-001` | error | failed | file | `skip-document` | 170 | Frontmatter YAMLの構文不正 |
| `FM-YAML-FORBIDDEN` | parse | `SPEC-FM-SCHEMA-001` | error | failed | file | `skip-document` | 171 | custom tag、anchor、alias、merge key、複雑key、複数document、重複mapping key |
| `FM-FIELD-TYPE` | parse | `SPEC-FM-SCHEMA-001` | error | failed | file | `skip-document` | 172 | Frontmatter fieldの型・値域、null・空値、配列重複、内部未知key |
| `FM-FIELD-REQUIRED` | parse | `SPEC-FM-REQUIRED-001` | error | failed | file | `skip-document` | 173 | Frontmatter必須field欠如 |
| `FM-FIELD-UNAVAILABLE` | parse | `SPEC-FM-UNAVAILABLE-001` | warning | passed_with_warnings | file | `continue` | 180 | 文書種別では利用できないCore field |
| `FM-FIELD-UNKNOWN` | parse | `SPEC-FM-UNKNOWN-001` | warning | passed_with_warnings | file | `continue` | 181 | `x-`で始まらない未知field |

## 4. EARS-AI、文書、関係

| conditionId | operations | code | severity | status | source | continuation | priority | 条件 |
|---|---|---|---|---|---|---|---:|---|
| `EAI-SYNTAX-CODE-UNCLOSED` | parse | `EAI-CORE-SYNTAX-005` | error | failed | file | `skip-document` | 200 | draft以外の未閉鎖code span |
| `EAI-SYNTAX-CODE-UNCLOSED-DRAFT` | parse | `EAI-CORE-SYNTAX-005` | warning | passed_with_warnings | file | `continue` | 200 | draftの未閉鎖code span |
| `EAI-SYNTAX-TAG-UNCLOSED` | parse | `EAI-CORE-SYNTAX-004` | error | failed | file | `skip-document` | 201 | draft以外の不正escape、未閉鎖quoted value、不正または未閉鎖tag |
| `EAI-SYNTAX-TAG-UNCLOSED-DRAFT` | parse | `EAI-CORE-SYNTAX-004` | warning | passed_with_warnings | file | `continue` | 201 | draftの不正escape、未閉鎖quoted value、不正または未閉鎖tag |
| `EAI-ID-FORMAT` | parse | `EAI-CORE-ID-001` | error | failed | file | `skip-document` | 202 | 規範文ID形式不正 |
| `EAI-ID-DUPLICATE` | parse | `EAI-CORE-ID-002` | error | failed | file | `skip-document` | 203 | 規範文ID重複 |
| `EAI-SYNTAX-TAG-ORDER` | parse | `EAI-CORE-SYNTAX-001` | error | failed | file | `skip-document` | 204 | draft以外のtag順序不正 |
| `EAI-SYNTAX-TAG-ORDER-DRAFT` | parse | `EAI-CORE-SYNTAX-001` | warning | passed_with_warnings | file | `continue` | 204 | draftのtag順序不正 |
| `EAI-SYNTAX-TAG-REQUIRED` | parse | `EAI-CORE-SYNTAX-002` | error | failed | file | `skip-document` | 205 | draft以外の必須tag不足 |
| `EAI-SYNTAX-TAG-REQUIRED-DRAFT` | parse | `EAI-CORE-SYNTAX-002` | warning | passed_with_warnings | file | `continue` | 205 | draftの必須tag不足 |
| `EAI-SYNTAX-TRIGGER-MULTIPLE` | parse | `EAI-CORE-SYNTAX-003` | error | failed | file | `skip-document` | 206 | draft以外の発動条件複数 |
| `EAI-SYNTAX-TRIGGER-MULTIPLE-DRAFT` | parse | `EAI-CORE-SYNTAX-003` | warning | passed_with_warnings | file | `continue` | 206 | draftの発動条件複数 |
| `EAI-SYNTAX-PERIOD-MISSING` | parse | `EAI-CORE-SYNTAX-006` | error | failed | file | `skip-document` | 207 | draft以外の句点欠落 |
| `EAI-SYNTAX-PERIOD-MISSING-DRAFT` | parse | `EAI-CORE-SYNTAX-006` | warning | passed_with_warnings | file | `continue` | 207 | draftの句点欠落 |
| `EAI-SEM-OPERAND-MISSING` | parse | `EAI-CORE-SEM-001` | error | failed | file | `skip-document` | 208 | draft以外のoperand不足 |
| `EAI-SEM-OPERAND-MISSING-DRAFT` | parse | `EAI-CORE-SEM-001` | warning | passed_with_warnings | file | `continue` | 208 | draftのoperand不足 |
| `EAI-SHOULD-REASON-MISSING` | parse | `EAI-CORE-SHOULD-001` | warning | passed_with_warnings | file | `continue` | 209 | `SHOULD`に`[REASON]` fieldがない |
| `EAI-EXTENSION-UNKNOWN` | parse | `EAI-EXT-UNKNOWN-001` | warning | passed_with_warnings | file | `continue` | 210 | 未知namespaceのopaque extension |
| `DOC-FILE-NAME-ID` | check | `SPEC-FILE-NAME-001` | error | failed | file | `skip-document` | 230 | file名IDとFrontmatter IDの不一致 |
| `DOC-ID-DUPLICATE` | parse | `SPEC-ID-DUPLICATE-001` | error | failed | file | `skip-document` | 231 | 文書ID重複 |
| `DOC-REQ-STATEMENT-EMPTY` | check | `SPEC-REQ-STATEMENT-001` | error | failed | file | `skip-document` | 232 | approved REQに妥当な規範文がない |
| `DOC-STYLE-H1` | check | `SPEC-STYLE-H1-001` | error | failed | file | `continue` | 240 | H1不在、複数、不一致 |
| `DOC-STYLE-SECTION` | check | `SPEC-STYLE-SECTION-001` | error | failed | file | `continue` | 241 | REQ必須section不在または空 |
| `DOC-STYLE-PLACEMENT` | check | `SPEC-STYLE-PLACEMENT-001` | error | failed | file | `continue` | 242 | 規範文が許可位置外 |
| `RELATION-LEGACY-REFS` | parse | `SPEC-RELATION-LEGACY-001` | error | failed | file | `skip-edge` | 300 | 旧`refs` field |
| `RELATION-TARGET-MISSING-STRONG` | context, check, verify | `SPEC-RELATION-MISSING-001` | error | failed | file | `skip-edge` | 310 | strong relation target不在 |
| `RELATION-TARGET-MISSING-RELATED` | context, check, verify | `SPEC-RELATION-ADVISORY-MISSING-001` | warning | passed_with_warnings | file | `skip-edge` | 311 | `related` target不在 |
| `RELATION-TYPE` | context, check, verify | `CTX-RELATION-TYPE-001` | error | failed | file | `skip-edge` | 320 | source／target型不適合 |
| `RELATION-CYCLE` | context, check, verify | `CTX-CYCLE-001` | error | failed | file | `skip-target` | 330 | `requires`または`refines`の禁止循環 |
| `TRACE-PATH-APPROVED` | check | `SPEC-PATH-INVALID-001` | error | failed | file | `continue` | 340 | approved文書のpath不正または不在 |
| `TRACE-PATH-DRAFT` | check | `SPEC-PATH-INVALID-001` | warning | passed_with_warnings | file | `continue` | 341 | draft文書の未作成予定path |
| `TRACE-COVERAGE-INVALID` | check | `SPEC-TEST-COVERAGE-001` | error | failed | file | `continue` | 342 | `covers` target不在または対応重複 |

## 5. Context、check、verify

| conditionId | operations | code | severity | status | source | continuation | priority | 条件 |
|---|---|---|---|---|---|---|---:|---|
| `CTX-ROOT-MISSING-EXPLICIT` | context, check, verify | `CTX-ROOT-MISSING-001` | error | failed | invocation | `skip-target` | 400 | 構文上妥当な明示起点IDまたはSPEC pathがcatalogに不在 |
| `CTX-ROOT-MISSING-DERIVED` | context, verify | `CTX-ROOT-MISSING-001` | error | failed | file | `skip-target` | 400 | TASK等から導出した起点ID不在 |
| `CTX-TASK-DEPENDENCY` | context, verify | `CTX-TASK-DEPENDENCY-001` | error | blocked | file | `skip-target` | 410 | 起点TASKの先行TASKが未done |
| `CTX-STATE-INAPPLICABLE` | context, verify | `CTX-STATE-001` | error | blocked | file | `skip-target` | 411 | 起点または強い依存先がpurposeに適用不能 |
| `CTX-STATE-SUPERSEDED` | context, verify | `CTX-STATE-SUPERSEDED-001` | error | blocked | file | `skip-target` | 412 | 起点または依存先が置換済み |
| `CTX-STATE-SUCCESSORS` | context, verify | `CTX-STATE-SUPERSEDED-002` | error | failed | file | `skip-target` | 413 | 有効な後継が複数 |
| `CTX-CLOSURE-LIMIT` | context, verify | `CTX-LIMIT-001` | error | blocked | file | `skip-target` | 420 | 完全Context閉包が文書数またはbyte上限超過 |
| `CTX-COVERAGE-TASK-MUST` | context | `CTX-COVERAGE-TASK-001` | warning | passed_with_warnings | file | `continue` | 430 | implement対象MUSTが未addressed |
| `CTX-COVERAGE-TASK-SHOULD` | context | `CTX-COVERAGE-TASK-001` | warning | passed_with_warnings | file | `continue` | 431 | implement対象SHOULDが未addressed |
| `CTX-COVERAGE-TEST-SHOULD` | context, verify | `CTX-COVERAGE-TEST-001` | warning | passed_with_warnings | file | `continue` | 432 | 対象SHOULDが未tested |
| `CTX-COVERAGE-TEST-MUST` | verify | `CTX-COVERAGE-TEST-001` | error | blocked | file | `skip-target` | 433 | 対象MUSTが未tested |
| `CTX-DIGEST-STALE` | context | `CTX-STALE-001` | error | blocked | invocation | `stop-operation` | 440 | expected Digest不一致 |
| `CTX-PROJECTION-OUTSIDE` | context | `CTX-PROJECTION-001` | error | failed | invocation | `stop-operation` | 441 | expand対象が完全解決集合外 |
| `CTX-PROJECTION-LIMIT` | context | `CTX-PROJECTION-LIMIT-001` | error | failed | invocation | `stop-operation` | 442 | detail／expandによる提示量hard limit超過 |
| `CHECK-STATE-TRANSITION` | check | `SPEC-STATE-TRANSITION-001` | error | failed | file | `continue` | 500 | 禁止状態遷移 |
| `CHECK-DOCUMENT-DELETED` | check | `SPEC-STATE-TRANSITION-001` | error | failed | file | `continue` | 501 | 管理済みSPEC削除 |
| `CHECK-APPROVED-MEANING` | check | `SPEC-SAFETY-APPROVED-001` | error | failed | file | `continue` | 510 | approved REQの意味変更時にstatusを戻していない |
| `CHECK-TASK-BOUNDARY` | check | `SPEC-TASK-BOUNDARY-001` | error | failed | file | `continue` | 520 | 明示TASKの境界外変更 |
| `CHECK-TASK-NO-GIT` | check | `SPEC-TASK-BOUNDARY-002` | error | blocked | environment | `stop-operation` | 521 | Git不在で明示TASK境界を検査不能 |
| `CHECK-IMPACT-OUTDATED` | check | `SPEC-IMPACT-OUTDATED-001` | warning | passed_with_warnings | file | `continue` | 530 | changed strong dependencyを持つapproved文書 |
| `CHECK-GIT-DEGRADED` | check | `SPEC-GIT-DEGRADED-001` | warning | passed_with_warnings | environment | `continue` | 540 | Git不在で差分依存保証を省略 |
| `VERIFY-BINDING-MISSING` | verify | `SPEC-VERIFY-BLOCKED-001` | error | blocked | file | `skip-target` | 600 | testまたはcommand定義不足 |
| `VERIFY-TARGETS-EMPTY` | verify | `SPEC-VERIFY-BLOCKED-002` | error | blocked | invocation | `stop-operation` | 601 | 単一workspaceまたは連合全体の対象0件 |
| `VERIFY-MEMBER-TARGETS-EMPTY` | verify | `SPEC-VERIFY-BLOCKED-002` | warning | passed_with_warnings | file | `skip-workspace` | 602 | 連合member単位の対象0件 |
| `VERIFY-SPAWN-ERROR` | verify | `SPEC-VERIFY-COMMAND-001` | error | error | environment | `skip-binding` | 610 | command起動不能 |
| `VERIFY-SIGNAL` | verify | `SPEC-VERIFY-COMMAND-001` | error | error | environment | `skip-binding` | 611 | commandがsignal終了 |
| `VERIFY-TIMEOUT` | verify | `SPEC-VERIFY-TIMEOUT-001` | error | error | environment | `skip-binding` | 612 | command timeout |
| `REPORT-WRITE` | check, verify | `SPEC-REPORT-WRITE-001` | error | error | file | `stop-operation` | 700 | 明示reportの排他的作成または書込み失敗 |

test commandが正常起動して非0で終了した場合はDiagnosticを生成しない。command結果の`termination: exit`と
非0`exitCode`がtarget、workspace、top-levelを`failed`へ集約する。

## 6. doctor

| conditionId | operations | code | severity | status | source | continuation | priority | 条件 |
|---|---|---|---|---|---|---|---:|---|
| `DOCTOR-RUNTIME-VERSION` | doctor | `SPEC-DOCTOR-CORE-001` | error | blocked | environment | `skip-check` | 800 | CPythonが下限未満 |
| `DOCTOR-CORE-START` | doctor | `SPEC-DOCTOR-CORE-002` | error | error | environment | `stop-operation` | 801 | Core実行体を起動不能 |
| `DOCTOR-PLUGIN-FORMAT` | doctor | `SPEC-DOCTOR-PLUGIN-001` | error | failed | environment | `skip-check` | 810 | plugin要求形式不正 |
| `DOCTOR-API-VERSION` | doctor | `SPEC-DOCTOR-API-001` | error | blocked | environment | `skip-check` | 811 | Core API非互換 |
| `DOCTOR-CAPABILITY` | doctor | `SPEC-DOCTOR-CAPABILITY-001` | error | blocked | environment | `skip-check` | 812 | required Capability不足 |
| `DOCTOR-WORKSPACE-MISSING` | doctor | `SPEC-DOCTOR-WORKSPACE-001` | error | blocked | environment | `skip-check` | 820 | `.spec/bitz.yaml`不在 |
| `DOCTOR-EARS-VERSION` | doctor | `SPEC-DOCTOR-EARS-001` | error | blocked | file | `skip-check` | 821 | EARS-AI major非互換 |
| `DOCTOR-GIT-DEGRADED` | doctor | `SPEC-DOCTOR-GIT-001` | warning | passed_with_warnings | environment | `continue` | 830 | 単一workspaceでGit不在または下限未満 |
| `DOCTOR-COMMAND-FILE` | doctor | `SPEC-DOCTOR-COMMAND-001` | error | blocked | file | `skip-check` | 840 | command実行fileを解決不能 |
| `DOCTOR-COMMAND-CWD` | doctor | `SPEC-DOCTOR-COMMAND-001` | error | blocked | file | `skip-check` | 841 | command cwdを解決不能 |

doctorの設定checkは§3の`CONFIG-*`条件を使用する。`SPEC-DOCTOR-CONFIG-001`は返さず、doctorの
`checks[]`にあるconfig項目が同じ`SPEC-CONFIG-SCHEMA-001` Diagnosticを参照する。

## 7. モノレポ連合

| conditionId | operations | code | severity | status | source | continuation | priority | 条件 |
|---|---|---|---|---|---|---|---:|---|
| `MONO-REF-QUALIFIER` | context, check, verify | `SPEC-MONOREPO-REF-001` | error | failed | file | `skip-edge` | 301 | 修飾ID構文不正 |
| `MONO-REF-UNQUALIFIED` | context, check, verify | `SPEC-MONOREPO-REF-001` | error | failed | file | `skip-edge` | 302 | targetが別workspaceだけに存在する非修飾参照 |
| `MONO-REF-WORKSPACE` | context, check, verify | `SPEC-MONOREPO-REF-001` | error | failed | file | `skip-edge` | 303 | 修飾workspace不在 |
| `MONO-OWNERSHIP` | context, check, verify | `SPEC-MONOREPO-OWNERSHIP-001` | error | failed | file | `skip-target` | 490 | SPEC、code、test、TASK、cwdの所有境界違反 |
| `MONO-CONFIG` | all | `SPEC-MONOREPO-CONFIG-001` | error | failed | file | `stop-federation` | 900 | `monorepo`の型、件数、配置、root条件不正 |
| `MONO-MEMBER` | all | `SPEC-MONOREPO-MEMBER-001` | error | failed | file | `stop-federation` | 910 | member設定不在、catalog ID不一致、nested federation |
| `MONO-ID` | all | `SPEC-MONOREPO-ID-001` | error | failed | file | `stop-federation` | 920 | workspace ID不正または重複 |
| `MONO-PATH` | all | `SPEC-MONOREPO-PATH-001` | error | failed | file | `stop-federation` | 930 | member path不正、重複、入れ子、symlink、submodule、別repository |
| `MONO-GIT` | all | `SPEC-MONOREPO-GIT-001` | error | blocked | environment | `stop-federation` | 940 | Git repository境界またはmember所有範囲を確定不能 |
| `MONO-VERSION` | all | `SPEC-MONOREPO-VERSION-001` | error | blocked | file | `stop-federation` | 950 | memberのSchemaまたはEARS-AIが未対応major |
| `MONO-UNREGISTERED` | all | `SPEC-MONOREPO-UNREGISTERED-001` | error | blocked | file | `stop-federation` | 960 | Git既知設定または選択設定がcatalogに未登録 |
| `MONO-LIMIT` | all | `SPEC-MONOREPO-LIMIT-001` | error | blocked | file | `stop-federation` | 970 | member数または連合snapshot resource上限超過 |
| `MONO-DEPENDENCY` | all | `SPEC-MONOREPO-DEPENDENCY-001` | error | blocked | file | `skip-workspace` | 980 | 別unitの非成功により依存処理を安全に継続不能 |

global preflightの同じraw原因に複数行が成立する場合は、設定構文・型、catalog、workspace ID、path、Git境界、
version、未登録設定、resource上限の順でprimaryを選ぶ。この列挙は上表のpriorityより優先する局所規則ではなく、
priority 900〜970を説明するものである。

## 8. 予約済みcode

次のcodeはCore 1.0の公開結果で使用しない。registryへ条件行を追加せず予約を維持する。

| code | 理由 |
|---|---|
| `EAI-CORE-ID-003` | Git全履歴を使うID再利用検出をCore 1.0から除外 |
| `EAI-CORE-LANG-001` | 自然言語を決定論的に識別しないためCore 1.0から除外 |
| `CTX-RELATION-MISSING-001` | `SPEC-RELATION-MISSING-001`へ統一 |
| `SPEC-BASE-AMBIGUOUS-001` | Coreがdefault branchやmerge-baseを推測しないため廃止 |
| `SPEC-DOCTOR-CONFIG-001` | `SPEC-CONFIG-SCHEMA-001`へ統一 |
| `SPEC-DOCTOR-CACHE-001` | Core 1.0が永続cacheを持たずcache検査を行わないため予約 |
