# 診断レジストリ

## 1. 本書の範囲

本書は、Core 1.0が操作の結果へ返す診断の条件についての、唯一の診断レジストリ（Diagnostic registry）である。各操作の仕様と仕様文書モデルの仕様は、
条件を検出する処理と補足情報を定めるが、`conditionId`、`code`、`severity`、`resultStatus`、発生元の種類、
継続単位（continuation）、主診断（primary Diagnostic）の優先順位を再定義しない。表にない条件から公開する診断を生成してはならない。

引数不正の終了コード4は、操作を始めず、診断を返さないため、本レジストリの対象外とする。
`doctor`の`checks[].status`は検査項目の単位の状態であり、診断の`resultStatus`とは別である。
`operations`の`parse`は、仕様文書の本文を解析する`context`、`check`、`verify`を表す。

## 2. フィールドと判定規則

| フィールド | 意味 |
|---|---|
| `conditionId` | 条件を識別する永続的なID。名称の変更や再利用を禁止する |
| `operations` | 条件を返しうる操作。`all`は4つの操作、`parse`は入力を解析する操作を表す |
| `code` | 公開する診断コード |
| `severity` | `info`、`warning`、`error` |
| `status` | 診断の`resultStatus` |
| `source` | `file`、`environment`、`invocation` |
| `continuation` | 診断を確定した後に処理を続けられる最小の単位 |
| `priority` | 同じ原因に複数の条件が成り立った場合の主診断の選択順。小さい値を優先する |

`continuation`は、次の閉じた語彙を使う。

| 値 | 意味 |
|---|---|
| `stop-operation` | 操作全体を停止する |
| `stop-multi-workspace` | 全体事前検査で停止し、メンバーの処理を始めない |
| `skip-workspace` | 当該のワークスペースに依存する処理を省略し、独立したワークスペースを続ける |
| `skip-document` | 当該の文書の後続の処理を省略し、独立した文書を続ける |
| `skip-edge` | 当該の関係のエッジの後続の解決だけを省略する |
| `skip-target` | 当該の対象のテスト割当てを実行せず、独立した対象を続ける |
| `skip-binding` | 当該のテスト割当てだけを実行せず、独立したテスト割当てを続ける |
| `skip-check` | 当該の`doctor`の検査項目だけを省略し、独立した検査項目を続ける |
| `continue` | 同じ処理単位の検査を続ける |

1つの元の原因から、同義の診断を複数生成しない。同じ処理単位で複数の条件の候補が同じ元の原因に対応する場合は、
`priority`が最小の行だけを主診断として返す。同じ`priority`の候補が残る場合は、本レジストリでより上にある行だけを返す。
独立した元の原因はそれぞれ主診断を持ち、結果の中の表示順は、結果・診断・終了コードの仕様の並べ替えの規則に従う。

関係のエッジ、または`covers`要素を単位とする診断の`evidence`の規則は
[結果・診断・終了コードの仕様 §4](01_結果・Diagnostic・終了コード.md#4-診断のスキーマ)を正とする。

## 3. 入力、設定、フロントマター

| `conditionId` | `operations` | `code` | `severity` | `status` | `source` | `continuation` | `priority` | 条件 |
|---|---|---|---|---|---|---|---:|---|
| `WORKSPACE-CONFIG-MISSING` | context, check, verify | `SPEC-WORKSPACE-MISSING-001` | error | blocked | environment | `stop-operation` | 90 | 探索範囲に`.spec/bitz.yaml`がない |
| `INPUT-IO-CONFIG` | all | `SPEC-INPUT-READ-001` | error | error | file | `stop-operation` | 100 | 設定ファイルの権限、I/O、読取り中の消失 |
| `INPUT-UTF8-CONFIG` | all | `SPEC-INPUT-READ-001` | error | failed | file | `stop-operation` | 110 | 設定ファイルをUTF-8として復号できない |
| `INPUT-IO-SPEC` | parse | `SPEC-INPUT-READ-001` | error | error | file | `skip-document` | 100 | 仕様文書のMarkdownの権限、I/O、読取り中の消失 |
| `INPUT-UTF8-SPEC` | parse | `SPEC-INPUT-READ-001` | error | failed | file | `skip-document` | 110 | 仕様文書のMarkdownをUTF-8として復号できない |
| `INPUT-BOM-CONFIG` | all | `SPEC-INPUT-BOM-001` | warning | passed_with_warnings | file | `continue` | 120 | 設定ファイルの先頭に既存のBOM |
| `INPUT-BOM-SPEC` | parse | `SPEC-INPUT-BOM-001` | warning | passed_with_warnings | file | `continue` | 120 | 仕様文書のMarkdownの先頭に既存のBOM |
| `INPUT-LIMIT-CONFIG` | all | `SPEC-INPUT-LIMIT-001` | error | failed | file | `stop-operation` | 130 | `bitz.yaml`が64 KiBを超過 |
| `INPUT-LIMIT-SPEC` | parse | `SPEC-INPUT-LIMIT-001` | error | failed | file | `skip-document` | 130 | 仕様文書のMarkdownが1 MiBを超過 |
| `INPUT-LIMIT-FRONTMATTER` | parse | `SPEC-INPUT-LIMIT-001` | error | failed | file | `skip-document` | 130 | フロントマターが32 KiBを超過 |
| `INPUT-LIMIT-SPEC-COUNT` | parse | `SPEC-INPUT-LIMIT-001` | error | failed | file | `stop-operation` | 130 | 単一ワークスペースの仕様文書のファイル数が10,000を超過 |
| `INPUT-LIMIT-STATEMENT-COUNT` | parse | `SPEC-INPUT-LIMIT-001` | error | failed | file | `skip-document` | 130 | 1つの文書の規範文の数が1,000を超過 |
| `INPUT-LIMIT-ARRAY-COUNT` | parse | `SPEC-INPUT-LIMIT-001` | error | failed | file | `skip-document` | 130 | 1つの文書の関係またはパスの配列の項目の数が1,000を超過 |
| `CONFIG-YAML-SYNTAX` | all | `SPEC-CONFIG-SCHEMA-001` | error | error | file | `stop-operation` | 140 | 設定のYAMLの構文が不正 |
| `CONFIG-YAML-FORBIDDEN` | all | `SPEC-CONFIG-SCHEMA-001` | error | error | file | `stop-operation` | 141 | 独自のタグ、アンカー、エイリアス、マージキー、複雑なキー、複数のYAML文書、重複したマッピングのキー |
| `CONFIG-FIELD-TYPE` | all | `SPEC-CONFIG-SCHEMA-001` | error | error | file | `stop-operation` | 142 | 設定のフィールドの型または値の範囲が不正 |
| `CONFIG-FIELD-REQUIRED` | all | `SPEC-CONFIG-SCHEMA-001` | error | error | file | `stop-operation` | 143 | 設定の必須のフィールドの欠如 |
| `CONFIG-SCHEMA-MAJOR` | all | `SPEC-CONFIG-SCHEMA-001` | error | blocked | file | `stop-operation` | 144 | 対応していないスキーマのメジャーバージョン |
| `EARS-SCHEMA-MAJOR` | context, check, verify | `SPEC-EARS-VERSION-001` | error | blocked | file | `stop-operation` | 145 | 対応していないEARS-AIのメジャーバージョン |
| `CONFIG-SCHEMA-MINOR-NEWER` | all | `SPEC-CONFIG-UNKNOWN-001` | warning | passed_with_warnings | file | `continue` | 149 | 同じメジャーバージョンで新しいスキーマのマイナーバージョン |
| `CONFIG-KEY-PROFILES` | all | `SPEC-CONFIG-UNKNOWN-001` | warning | passed_with_warnings | file | `continue` | 150 | 予約されたキー`profiles` |
| `CONFIG-KEY-UNKNOWN` | all | `SPEC-CONFIG-UNKNOWN-001` | warning | passed_with_warnings | file | `continue` | 151 | 同じメジャーバージョンの未知の標準のキー |
| `WORKSPACE-ENTRY-UNKNOWN` | check, doctor | `SPEC-WORKSPACE-UNKNOWN-001` | warning | passed_with_warnings | file | `continue` | 160 | `.spec/`の中の未知のファイルまたはディレクトリ |
| `FM-YAML-SYNTAX` | parse | `SPEC-FM-SCHEMA-001` | error | failed | file | `skip-document` | 170 | フロントマターのYAMLの構文が不正 |
| `FM-YAML-FORBIDDEN` | parse | `SPEC-FM-SCHEMA-001` | error | failed | file | `skip-document` | 171 | 独自のタグ、アンカー、エイリアス、マージキー、複雑なキー、複数のYAML文書、重複したマッピングのキー |
| `FM-FIELD-TYPE` | parse | `SPEC-FM-SCHEMA-001` | error | failed | file | `skip-document` | 172 | フロントマターのフィールドの型・値の範囲、`null`・空の値、配列の重複、内部の未知のキー |
| `FM-FIELD-REQUIRED` | parse | `SPEC-FM-REQUIRED-001` | error | failed | file | `skip-document` | 173 | フロントマターの必須のフィールドの欠如 |
| `FM-FIELD-UNAVAILABLE` | parse | `SPEC-FM-UNAVAILABLE-001` | warning | passed_with_warnings | file | `continue` | 180 | 文書種別では利用できないCoreのフィールド |
| `FM-FIELD-UNKNOWN` | parse | `SPEC-FM-UNKNOWN-001` | warning | passed_with_warnings | file | `continue` | 181 | `x-`で始まらない未知のフィールド |

## 4. EARS-AI、文書、関係

| `conditionId` | `operations` | `code` | `severity` | `status` | `source` | `continuation` | `priority` | 条件 |
|---|---|---|---|---|---|---|---:|---|
| `EAI-SYNTAX-CODE-UNCLOSED` | parse | `EAI-CORE-SYNTAX-005` | error | failed | file | `skip-document` | 200 | `draft`以外の未閉鎖のコードスパン |
| `EAI-SYNTAX-CODE-UNCLOSED-DRAFT` | parse | `EAI-CORE-SYNTAX-005` | warning | passed_with_warnings | file | `continue` | 200 | `draft`の未閉鎖のコードスパン |
| `EAI-SYNTAX-TAG-UNCLOSED` | parse | `EAI-CORE-SYNTAX-004` | error | failed | file | `skip-document` | 201 | `draft`以外の不正なエスケープ、未閉鎖の引用値、不正または未閉鎖のタグ |
| `EAI-SYNTAX-TAG-UNCLOSED-DRAFT` | parse | `EAI-CORE-SYNTAX-004` | warning | passed_with_warnings | file | `continue` | 201 | `draft`の不正なエスケープ、未閉鎖の引用値、不正または未閉鎖のタグ |
| `EAI-ID-FORMAT` | parse | `EAI-CORE-ID-001` | error | failed | file | `skip-document` | 202 | 規範文IDの形式が不正 |
| `EAI-ID-DOCUMENT-MISMATCH` | parse | `EAI-CORE-ID-001` | error | failed | file | `skip-document` | 202 | 規範文IDの文書部分がフロントマターの`id`と一致しない。`draft`でも`error`とする |
| `EAI-ID-DUPLICATE` | parse | `EAI-CORE-ID-002` | error | failed | file | `skip-document` | 203 | 規範文IDの重複 |
| `EAI-SYNTAX-TAG-ORDER` | parse | `EAI-CORE-SYNTAX-001` | error | failed | file | `skip-document` | 204 | `draft`以外のタグの順序が不正 |
| `EAI-SYNTAX-TAG-ORDER-DRAFT` | parse | `EAI-CORE-SYNTAX-001` | warning | passed_with_warnings | file | `continue` | 204 | `draft`のタグの順序が不正 |
| `EAI-SYNTAX-TAG-REQUIRED` | parse | `EAI-CORE-SYNTAX-002` | error | failed | file | `skip-document` | 205 | `draft`以外の必須のタグの不足 |
| `EAI-SYNTAX-TAG-REQUIRED-DRAFT` | parse | `EAI-CORE-SYNTAX-002` | warning | passed_with_warnings | file | `continue` | 205 | `draft`の必須のタグの不足 |
| `EAI-SYNTAX-TRIGGER-MULTIPLE` | parse | `EAI-CORE-SYNTAX-003` | error | failed | file | `skip-document` | 206 | `draft`以外の発動条件が複数 |
| `EAI-SYNTAX-TRIGGER-MULTIPLE-DRAFT` | parse | `EAI-CORE-SYNTAX-003` | warning | passed_with_warnings | file | `continue` | 206 | `draft`の発動条件が複数 |
| `EAI-SYNTAX-PERIOD-MISSING` | parse | `EAI-CORE-SYNTAX-006` | error | failed | file | `skip-document` | 207 | `draft`以外の句点の欠落 |
| `EAI-SYNTAX-PERIOD-MISSING-DRAFT` | parse | `EAI-CORE-SYNTAX-006` | warning | passed_with_warnings | file | `continue` | 207 | `draft`の句点の欠落 |
| `EAI-SEM-OPERAND-MISSING` | parse | `EAI-CORE-SEM-001` | error | failed | file | `skip-document` | 208 | `draft`以外のオペランドの不足 |
| `EAI-SEM-OPERAND-MISSING-DRAFT` | parse | `EAI-CORE-SEM-001` | warning | passed_with_warnings | file | `continue` | 208 | `draft`のオペランドの不足 |
| `EAI-SHOULD-REASON-MISSING` | parse | `EAI-CORE-SHOULD-001` | warning | passed_with_warnings | file | `continue` | 209 | `SHOULD`に`[REASON]`のフィールドがない |
| `EAI-EXTENSION-UNKNOWN` | parse | `EAI-EXT-UNKNOWN-001` | warning | passed_with_warnings | file | `continue` | 210 | 未知の名前空間の不透明な拡張タグ |
| `DOC-FILE-NAME-ID` | check | `SPEC-FILE-NAME-001` | error | failed | file | `skip-document` | 230 | ファイル名のIDとフロントマターのIDの不一致 |
| `DOC-ID-DUPLICATE` | parse | `SPEC-ID-DUPLICATE-001` | error | failed | file | `skip-document` | 231 | 文書IDの重複 |
| `DOC-REQ-STATEMENT-EMPTY` | check | `SPEC-REQ-STATEMENT-001` | error | failed | file | `skip-document` | 232 | `approved`のREQに妥当な規範文がない |
| `DOC-STYLE-H1` | check | `SPEC-STYLE-H1-001` | error | failed | file | `continue` | 240 | H1の不在、複数、不一致 |
| `DOC-STYLE-SECTION` | check | `SPEC-STYLE-SECTION-001` | error | failed | file | `continue` | 241 | REQの必須の節が不在または空 |
| `DOC-STYLE-PLACEMENT` | check | `SPEC-STYLE-PLACEMENT-001` | error | failed | file | `continue` | 242 | 規範文が許可された位置の外 |
| `RELATION-LEGACY-REFS` | parse | `SPEC-RELATION-LEGACY-001` | error | failed | file | `skip-edge` | 300 | 旧`refs`のフィールド |
| `RELATION-TARGET-MISSING-STRONG` | context, check, verify | `SPEC-RELATION-MISSING-001` | error | failed | file | `skip-edge` | 310 | 強い関係の参照先の不在 |
| `RELATION-TARGET-MISSING-RELATED` | context, check, verify | `SPEC-RELATION-ADVISORY-MISSING-001` | warning | passed_with_warnings | file | `skip-edge` | 311 | `related`の参照先の不在 |
| `RELATION-TYPE` | context, check, verify | `CTX-RELATION-TYPE-001` | error | failed | file | `skip-edge` | 320 | 参照元と参照先の型の組合せが不適合 |
| `RELATION-CYCLE` | context, check, verify | `CTX-CYCLE-001` | error | failed | file | `skip-target` | 330 | `requires`または`refines`による禁止された循環 |
| `TRACE-PATH-APPROVED` | check | `SPEC-PATH-INVALID-001` | error | failed | file | `continue` | 340 | `approved`の文書のパスが不正または不在 |
| `TRACE-PATH-DRAFT` | check | `SPEC-PATH-INVALID-001` | warning | passed_with_warnings | file | `continue` | 341 | `draft`の文書の、未作成の予定パス |
| `TRACE-COVERAGE-INVALID` | check | `SPEC-TEST-COVERAGE-001` | error | failed | file | `continue` | 342 | `covers`の参照先が不在、または対応が重複 |

## 5. コンテキスト、`check`、`verify`

| `conditionId` | `operations` | `code` | `severity` | `status` | `source` | `continuation` | `priority` | 条件 |
|---|---|---|---|---|---|---|---:|---|
| `CTX-ROOT-MISSING-EXPLICIT` | context, check, verify | `CTX-ROOT-MISSING-001` | error | failed | invocation | `skip-target` | 400 | 構文上は妥当な、明示した起点IDまたは仕様文書のパスがカタログにない |
| `CTX-ROOT-MISSING-DERIVED` | context, verify | `CTX-ROOT-MISSING-001` | error | failed | file | `skip-target` | 400 | TASKなどから導いた起点IDが不在 |
| `CTX-TASK-DEPENDENCY` | context, verify | `CTX-TASK-DEPENDENCY-001` | error | blocked | file | `skip-target` | 410 | 起点のTASKの先行するTASKが`done`でない |
| `CTX-STATE-INAPPLICABLE` | context, verify | `CTX-STATE-001` | error | blocked | file | `skip-target` | 411 | 起点または強い関係の参照先が、目的に適用できない |
| `CTX-STATE-SUPERSEDED` | context, verify | `CTX-STATE-SUPERSEDED-001` | error | blocked | file | `skip-target` | 412 | 起点または依存の参照先が置換済み |
| `CTX-STATE-SUCCESSORS` | context, verify | `CTX-STATE-SUPERSEDED-002` | error | failed | file | `skip-target` | 413 | 有効な後継が複数 |
| `CTX-CLOSURE-LIMIT` | context, verify | `CTX-LIMIT-001` | error | blocked | file | `skip-target` | 420 | コンテキストの完全な閉包が、文書数またはバイト数の上限を超過 |
| `CTX-COVERAGE-TASK-MUST` | context | `CTX-COVERAGE-TASK-001` | warning | passed_with_warnings | file | `continue` | 430 | 目的が`implement`の対象規範文の`MUST`が未対応 |
| `CTX-COVERAGE-TASK-SHOULD` | context | `CTX-COVERAGE-TASK-001` | warning | passed_with_warnings | file | `continue` | 431 | 目的が`implement`の対象規範文の`SHOULD`が未対応 |
| `CTX-COVERAGE-TEST-SHOULD` | context, verify | `CTX-COVERAGE-TEST-001` | warning | passed_with_warnings | file | `continue` | 432 | 目的が`implement`または`verify`の対象規範文の`SHOULD`が未テスト |
| `CTX-COVERAGE-TEST-MUST` | context, verify | `CTX-COVERAGE-TEST-001` | error | blocked | file | `skip-target` | 433 | 目的が`verify`の対象規範文の`MUST`が未テスト |
| `CTX-COVERAGE-TEST-MUST-IMPLEMENT` | context | `CTX-COVERAGE-TEST-001` | warning | passed_with_warnings | file | `continue` | 434 | 目的が`implement`の対象規範文の`MUST`が未テスト |
| `CTX-DIGEST-STALE` | context | `CTX-STALE-001` | error | blocked | invocation | `stop-operation` | 440 | 期待したハッシュ値との不一致 |
| `CTX-PROJECTION-OUTSIDE` | context | `CTX-PROJECTION-001` | error | failed | invocation | `stop-operation` | 441 | `--expand`の対象が完全解決した集合の外 |
| `CTX-PROJECTION-LIMIT` | context | `CTX-PROJECTION-LIMIT-001` | error | failed | invocation | `stop-operation` | 442 | 詳細度または展開指定が原因で、提示量が絶対上限を超過 |
| `CHECK-STATE-TRANSITION` | check | `SPEC-STATE-TRANSITION-001` | error | failed | file | `continue` | 500 | 禁止された状態遷移 |
| `CHECK-DOCUMENT-DELETED` | check | `SPEC-STATE-TRANSITION-001` | error | failed | file | `continue` | 501 | 管理済みの仕様文書の削除 |
| `CHECK-APPROVED-MEANING` | check | `SPEC-SAFETY-APPROVED-001` | error | failed | file | `continue` | 510 | `approved`のREQの意味を変えたときに、状態を戻していない |
| `CHECK-TASK-BOUNDARY` | check | `SPEC-TASK-BOUNDARY-001` | error | failed | file | `continue` | 520 | 明示したTASKの境界の外の変更 |
| `CHECK-TASK-NO-GIT` | check | `SPEC-TASK-BOUNDARY-002` | error | blocked | environment | `stop-operation` | 521 | Git不在のため、明示したTASKの境界を検査できない |
| `CHECK-IMPACT-OUTDATED` | check | `SPEC-IMPACT-OUTDATED-001` | warning | passed_with_warnings | file | `continue` | 530 | 変更があったものへ強く依存する`approved`の文書 |
| `CHECK-GIT-DEGRADED` | check | `SPEC-GIT-DEGRADED-001` | warning | passed_with_warnings | environment | `continue` | 540 | Git不在のため、差分に依存する保証を省く |
| `VERIFY-BINDING-MISSING` | verify | `SPEC-VERIFY-BLOCKED-001` | error | blocked | file | `skip-target` | 600 | テストまたはコマンドの定義の不足 |
| `VERIFY-TARGETS-EMPTY` | verify | `SPEC-VERIFY-BLOCKED-002` | error | blocked | invocation | `stop-operation` | 601 | 単一ワークスペース、または複合ワークスペース全体の対象が0件 |
| `VERIFY-MEMBER-TARGETS-EMPTY` | verify | `SPEC-VERIFY-BLOCKED-002` | warning | passed_with_warnings | file | `skip-workspace` | 602 | 複合ワークスペースのメンバー単位の対象が0件 |
| `VERIFY-ARGV-EXPANDED-LIMIT` | verify | `SPEC-VERIFY-BLOCKED-001` | error | blocked | file | `skip-binding` | 603 | `{tests}`を展開した後の引数列が、要素数またはバイト数の上限を超過 |
| `VERIFY-CWD-UNAVAILABLE` | verify | `SPEC-VERIFY-BLOCKED-001` | error | blocked | file | `skip-binding` | 604 | コマンドの作業ディレクトリが不在、または実行時に利用できない |
| `VERIFY-EXECUTABLE-UNAVAILABLE` | verify | `SPEC-VERIFY-BLOCKED-001` | error | blocked | environment | `skip-binding` | 605 | `PATH`または明示したパスから、通常の実行可能ファイルを解決できない |
| `VERIFY-CONFIG-UNTRACKED` | verify | `SPEC-VERIFY-BLOCKED-001` | error | blocked | file | `skip-binding` | 606 | Gitが利用できるときに、テスト割当てを所有するワークスペースの設定ファイルがインデックスで未追跡 |
| `VERIFY-TEST-OUTSIDE-CWD` | verify | `SPEC-VERIFY-BLOCKED-001` | error | blocked | file | `skip-binding` | 607 | 存在と所有境界が妥当なテストのパスが、実効の作業ディレクトリの配下にない |
| `VERIFY-SPAWN-ERROR` | verify | `SPEC-VERIFY-COMMAND-001` | error | error | environment | `skip-binding` | 610 | 起動前検査を通過した後の競合状態、リソースの不足、OSのエラーでプロセスの生成に失敗 |
| `VERIFY-SIGNAL` | verify | `SPEC-VERIFY-COMMAND-001` | error | error | environment | `skip-binding` | 611 | コマンドがシグナルで終了 |
| `VERIFY-TIMEOUT` | verify | `SPEC-VERIFY-TIMEOUT-001` | error | error | environment | `skip-binding` | 612 | コマンドのタイムアウト |
| `REPORT-WRITE` | check, verify | `SPEC-REPORT-WRITE-001` | error | error | file | `stop-operation` | 700 | 明示したレポートの排他的な作成または書込みの失敗。レポートのディレクトリがディレクトリ以外、またはシンボリックリンクの場合を含む |

テストコマンドが正常に起動して非0で終了した場合は、診断を生成しない。コマンドの結果の`termination: exit`と
非0の`exitCode`が、検証対象、ワークスペース、最上位を`failed`へ集約する。

## 6. `doctor`

| `conditionId` | `operations` | `code` | `severity` | `status` | `source` | `continuation` | `priority` | 条件 |
|---|---|---|---|---|---|---|---:|---|
| `DOCTOR-RUNTIME-VERSION` | doctor | `SPEC-DOCTOR-CORE-001` | error | blocked | environment | `skip-check` | 800 | CPythonが下限未満 |
| `DOCTOR-CORE-START` | doctor | `SPEC-DOCTOR-CORE-002` | error | error | environment | `stop-operation` | 801 | Coreの実行体を起動できない |
| `DOCTOR-PLUGIN-FORMAT` | doctor | `SPEC-DOCTOR-PLUGIN-001` | error | failed | environment | `skip-check` | 810 | プラグインの要求形式が不正 |
| `DOCTOR-API-VERSION` | doctor | `SPEC-DOCTOR-API-001` | error | blocked | environment | `skip-check` | 811 | CoreのAPIが非互換 |
| `DOCTOR-CAPABILITY` | doctor | `SPEC-DOCTOR-CAPABILITY-001` | error | blocked | environment | `skip-check` | 812 | 必須の対応機能の不足 |
| `DOCTOR-WORKSPACE-MISSING` | doctor | `SPEC-DOCTOR-WORKSPACE-001` | error | blocked | environment | `skip-check` | 820 | `.spec/bitz.yaml`が不在 |
| `DOCTOR-EARS-VERSION` | doctor | `SPEC-DOCTOR-EARS-001` | error | blocked | file | `skip-check` | 821 | EARS-AIのメジャーバージョンが非互換 |
| `DOCTOR-GIT-DEGRADED` | doctor | `SPEC-DOCTOR-GIT-001` | warning | passed_with_warnings | environment | `continue` | 830 | 単一ワークスペースでGit不在、または下限未満 |
| `DOCTOR-COMMAND-FILE` | doctor | `SPEC-DOCTOR-COMMAND-001` | error | blocked | file | `skip-check` | 840 | コマンドの実行ファイルを解決できない |
| `DOCTOR-COMMAND-CWD` | doctor | `SPEC-DOCTOR-COMMAND-001` | error | blocked | file | `skip-check` | 841 | コマンドの作業ディレクトリを解決できない |

`doctor`の設定の検査項目は、§3の`CONFIG-*`の条件を使う。`SPEC-DOCTOR-CONFIG-001`は返さず、`doctor`の
`checks[]`にある設定の項目が、同じ`SPEC-CONFIG-SCHEMA-001`の診断を参照する。

## 7. 複合ワークスペース

| `conditionId` | `operations` | `code` | `severity` | `status` | `source` | `continuation` | `priority` | 条件 |
|---|---|---|---|---|---|---|---:|---|
| `MULTI-REF-QUALIFIER` | context, check, verify | `SPEC-MULTI-REF-001` | error | failed | file | `skip-edge` | 301 | 修飾IDの構文が不正 |
| `MULTI-REF-UNQUALIFIED` | context, check, verify | `SPEC-MULTI-REF-001` | error | failed | file | `skip-edge` | 302 | 参照先が別のワークスペースだけに存在する非修飾の参照 |
| `MULTI-REF-WORKSPACE` | context, check, verify | `SPEC-MULTI-REF-001` | error | failed | file | `skip-edge` | 303 | 修飾したワークスペースが不在 |
| `MULTI-OWNERSHIP` | context, check, verify | `SPEC-MULTI-OWNERSHIP-001` | error | failed | file | `skip-target` | 490 | 仕様文書、コード、テスト、TASK、作業ディレクトリの所有境界の違反 |
| `MULTI-CONFIG` | all | `SPEC-MULTI-CONFIG-001` | error | failed | file | `stop-multi-workspace` | 900 | `multiWorkspace`の型、件数、配置、ルートの条件が不正 |
| `MULTI-MEMBER` | all | `SPEC-MULTI-MEMBER-001` | error | failed | file | `stop-multi-workspace` | 910 | メンバーの設定が不在、カタログのIDと不一致、入れ子の複合ワークスペース |
| `MULTI-ID` | all | `SPEC-MULTI-ID-001` | error | failed | file | `stop-multi-workspace` | 920 | ワークスペースIDが不正または重複 |
| `MULTI-PATH` | all | `SPEC-MULTI-PATH-001` | error | failed | file | `stop-multi-workspace` | 930 | メンバーのパスが不正、重複、入れ子、シンボリックリンク、サブモジュール、別のリポジトリ |
| `MULTI-GIT` | all | `SPEC-MULTI-GIT-001` | error | blocked | environment | `stop-multi-workspace` | 940 | Gitのリポジトリの境界、またはメンバーの所有領域を確定できない |
| `MULTI-VERSION` | all | `SPEC-MULTI-VERSION-001` | error | blocked | file | `stop-multi-workspace` | 950 | メンバーのスキーマまたはEARS-AIが、対応していないメジャーバージョン |
| `MULTI-UNREGISTERED` | all | `SPEC-MULTI-UNREGISTERED-001` | error | blocked | file | `stop-multi-workspace` | 960 | Gitが認識している設定、または選択した設定がカタログに未登録 |
| `MULTI-LIMIT` | all | `SPEC-MULTI-LIMIT-001` | error | blocked | file | `stop-multi-workspace` | 970 | メンバーの数、または複合ワークスペースのスナップショットのリソースの上限を超過 |
| `MULTI-DEPENDENCY` | context, verify | `SPEC-MULTI-DEPENDENCY-001` | error | blocked | file | `skip-target` | 980 | 具体的な診断のない対象が、別の単位の非成功によりコンテキストまたはテスト割当てを構成できない |
| `MULTI-DEPENDENCY-DOCTOR` | doctor | `SPEC-MULTI-DEPENDENCY-001` | error | blocked | file | `skip-check` | 980 | 具体的な診断のない`doctor`の検査項目が、別の単位の非成功により依存する出力を得られない |

`check`は、依存先を解釈できない参照元へ具体的な関係の診断を返し、上の依存遮断（dependency blocking）を追加しない。
`context`は一部が欠けたコンテキスト一式を成功にせず、`verify`は独立した検証対象とテスト割当て、`doctor`は独立した検査項目を続ける。

全体事前検査の同じ元の原因に複数の行が成り立つ場合は、設定の構文・型、カタログ、ワークスペースID、パス、Gitの境界、
バージョン、未登録の設定、リソースの上限の順で主診断を選ぶ。この列挙は、上の表の`priority`より優先する局所的な規則ではなく、
`priority`の900〜970を説明するものである。

## 8. 予約済みコード

次の予約済みコード（reserved code）は、Core 1.0の公開する結果で使わない。レジストリへ条件の行を加えず、予約を保つ。

| `code` | 理由 |
|---|---|
| `EAI-CORE-ID-003` | Gitの全履歴を使うIDの再利用の検出を、Core 1.0から除外する |
| `EAI-CORE-LANG-001` | 自然言語を決定論的に識別しないため、Core 1.0から除外する |
| `CTX-RELATION-MISSING-001` | `SPEC-RELATION-MISSING-001`へ統一する |
| `SPEC-BASE-AMBIGUOUS-001` | Coreが既定のブランチやマージベースを推測しないため、廃止する |
| `SPEC-DOCTOR-CONFIG-001` | `SPEC-CONFIG-SCHEMA-001`へ統一する |
| `SPEC-DOCTOR-CACHE-001` | Core 1.0が永続的なキャッシュを持たず、キャッシュの検査を行わないため予約する |
