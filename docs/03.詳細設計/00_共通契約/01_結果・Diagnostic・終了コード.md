# 結果・Diagnostic・終了コード

## 1. 所有範囲

本書は全Core操作が共有する結果外形、status、Diagnostic Schema、終了コード、report生成条件を定義する。
Diagnostic条件と公開値は[Diagnostic registry](05_Diagnostic-registry.md)、操作固有fieldと検出処理は各操作仕様が定義する。
機械可読な正本は[`fixtures/conformance/result.schema.json`](../../../fixtures/conformance/result.schema.json)とし、
本文の表・例とSchemaが異なる場合は不適合として同じ変更で修正する。

## 2. 共通結果

```json
{
  "schemaVersion": "1.0",
  "operation": "check",
  "status": "passed",
  "scope": "changed",
  "workspace": {"id": "root", "path": "."},
  "revision": {
    "base": "89abcdef0123456789abcdef0123456789abcdef",
    "commit": "0123456789abcdef0123456789abcdef01234567",
    "dirty": true
  },
  "selection": {"changedPathCount": 3, "targetDocumentCount": 1, "excludedCodeTestPathCount": 2},
  "durationMs": 184,
  "diagnostics": []
}
```

| field | 型 | 必須 | 意味 |
|---|---|:--:|---|
| `schemaVersion` | string | Yes | 結果Schema major.minor |
| `operation` | enum | Yes | `context`、`check`、`verify`、`doctor` |
| `status` | enum | Yes | 操作全体のstatus |
| `scope` | string | check／verifyだけYes | checkは`changed`、`selected`、`full`、`all-workspaces`、verifyは`selected`、`all`、`all-workspaces` |
| `workspace` | object | workspace単独操作でYes | 対象またはrequest workspaceの`id`と`path`。identity確定前だけ`id: null` |
| `federation` | object | 全体操作でYes | federation rootの`id`と`path: "."`。root identity不成立時だけ`id: null` |
| `workspaces` | array | 全体操作でYes | 処理順のworkspace別結果。操作固有fieldを保持 |
| `revision` | object/null | context／check／verifyでYes | Git基準版と実行時状態。doctorでは禁止 |
| `durationMs` | integer | Yes | 非負の経過ms |
| `diagnostics` | array | Yes | 0件以上のDiagnostic |

Core 1.0 producerはSchemaにないfieldを出力しない。consumerは同じmajorの新しいminorにある未知fieldを
保持または無視できる。未知majorは`blocked`として処理を続けない。
各公開objectは未知fieldを禁止する。ただし、正規化Frontmatter、Diagnostic `extensions`、`evidence`のように
別契約またはopaque値が内容を所有するfieldだけは、その所有契約のkeyを許可する。配列順は各fieldの所有仕様に従い、
適合fixtureではkeyの有無、null、空配列、要素順を含めて比較する。

操作と結果variantの必須fieldを次に固定する。表にないvariantは存在しない。

| operation | variant | 必須の識別・操作field |
|---|---|---|
| context | workspace-local | `workspace`、`purpose`、`roots`、`contextDigest`、`revision`、`resolution`、`projection`、`documents`、`constraintLedger`、`coverage`。連合固有field禁止 |
| context | workspace-federated | localと同じfieldに加え`documents[].workspaceId`、`resolution.workspaces`、`resolution.crossWorkspaceEdges` |
| check | workspace | `workspace`、`scope`、`revision`。`changed`は`selection`、`selected`／`full`は2つのchecked count |
| check | federation | `federation`、`workspaces`、`scope: all-workspaces`、`revision` |
| verify | workspace | `workspace`、`scope`、`targetResults`、`commands`、`revision` |
| verify | federation | `federation`、`workspaces`、`scope: all-workspaces`、`revision` |
| doctor | workspace | `workspace`、`core`、`checks` |
| doctor | federation | `federation`、`workspaces`、`core`、`checks` |

`contextDigest`は完全Contextを構成できない場合だけnullとする。`revision`の規則は次のとおりである。

- context／verifyの非null objectは40桁小文字16進`commit`とboolean `dirty`だけを持つ。
- checkの非null objectは同形式の`base`、`commit`とboolean `dirty`を持つ。
- 単一workspaceでGit不在またはunborn repositoryなら`revision: null`とする。解決不能な明示`--base`は
  結果を作らない終了コード4であり、nullへ縮退しない。
- checkの`scope: changed`は解決済みGit基準版を必要とするためrevisionをnullにしない。Git不在／unbornの縮退結果は
  `scope: full`とする。
- 連合check／verifyはGit境界確定がpreflight条件であるため`revision`をnullにしない。
- doctorはGit状態をcheck itemで報告し、`revision` fieldを出力しない。

非成功でも選択したvariantの必須fieldを省略しない。設定の構文・型・ID不正など、workspace identityを構成する前に
停止した単独結果だけ`workspace.id`をnullとし、`path`は発見したworkspace候補のrepository root相対pathとする。
処理開始前に停止した派生配列は空、派生件数は0とする。contextは`contextDigest: null`、
`resolution.complete: false`、空の`documents`とLedger／coverageを返す。これは部分結果の成功を意味せず、
実際に完了した処理量だけを表す。identity確定後はtop-levelと入れ子の全workspace IDをstringにする。

単一workspaceでは設定した`workspace.id`、省略時は`root`を使い、pathを`.`とする。連合内のworkspace単独操作では
実際のworkspace IDとrepository root相対pathを返す。`--all-workspaces`結果は`workspace`を持たず、
`federation`と`workspaces`を持つ。top-level statusはtop-level Diagnosticと全workspace結果へ同じ最悪値規則を
適用して集約する。

| `federation` field | 型 | 必須 | 意味 |
|---|---|:--:|---|
| `id` | string/null | Yes | 有効なfederation root ID。identity確定前のglobal preflight失敗時だけnull |
| `path` | string | Yes | 常に`.` |

`workspaces`はglobal preflightが非成功でmember処理を開始しない場合だけ空配列にできる。処理開始後は
federation rootを先頭、その後をworkspace ID辞書順に保持する。

```json
{
  "schemaVersion": "1.0",
  "operation": "check",
  "scope": "all-workspaces",
  "status": "passed",
  "federation": {"id": "platform", "path": "."},
  "workspaces": [
    {"id": "platform", "path": ".", "status": "passed", "checkedDocumentCount": 20, "checkedStatementCount": 40, "durationMs": 40, "diagnostics": []},
    {"id": "api", "path": "services/api", "status": "passed", "checkedDocumentCount": 25, "checkedStatementCount": 50, "durationMs": 50, "diagnostics": []},
    {"id": "web", "path": "apps/web", "status": "passed", "checkedDocumentCount": 30, "checkedStatementCount": 60, "durationMs": 52, "diagnostics": []}
  ],
  "revision": {"base": "89abcdef0123456789abcdef0123456789abcdef", "commit": "0123456789abcdef0123456789abcdef01234567", "dirty": true},
  "durationMs": 142,
  "diagnostics": []
}
```

`workspaces`は実行順を維持し、各要素に操作固有fieldを追加する。top-level `diagnostics`はcatalog、横断関係、
集約自体のDiagnosticだけを持ち、member Diagnosticを複製しない。件数と所要時間は単純和とし、同じ実行実体を
重複加算しない。

| `workspaces[]` field | 型 | 必須 | 意味 |
|---|---|:--:|---|
| `id` | string | Yes | workspace ID |
| `path` | string | Yes | repository root相対path。federation rootは`.` |
| `status` | enum | Yes | workspace単位status |
| `durationMs` | integer | Yes | workspace単位の非負経過ms |
| `diagnostics` | array | Yes | 当該workspaceが所有するDiagnostic |

全体操作の操作固有fieldは次を必須とする。配列は0件でも省略しない。

| 操作 | top-level field | `workspaces[]` field |
|---|---|---|
| check | `scope: "all-workspaces"`、`revision` | 非負integer `checkedDocumentCount`、`checkedStatementCount` |
| verify | `scope: "all-workspaces"`、`revision` | `targetResults[]`、`commands[]` |
| doctor | `core`、global `checks[]` | workspace固有`checks[]` |

check／verifyの`revision`はrepository全体で1件だけをtop-levelへ置き、workspace要素へ複製しない。verify commandは
owner workspaceの`commands[]`へ1件だけ置く。top-levelへ操作固有件数を重複して持たず、workspace countまたは配列から
導出する。各操作の完全な全体結果例を次に示す。

### 2.1 check全体結果

上記JSON例をcheck全体結果の正規外形とする。`checkedDocumentCount`は当該workspaceで完全検査したSPEC文書数、
`checkedStatementCount`は完全検査した規範文数である。

### 2.2 verify全体結果

```json
{
  "schemaVersion": "1.0",
  "operation": "verify",
  "scope": "all-workspaces",
  "status": "passed_with_warnings",
  "federation": {"id": "platform", "path": "."},
  "workspaces": [
    {
      "id": "platform",
      "path": ".",
      "status": "passed_with_warnings",
      "targetResults": [],
      "commands": [],
      "durationMs": 20,
      "diagnostics": [
        {
          "code": "SPEC-VERIFY-BLOCKED-002",
          "severity": "warning",
          "resultStatus": "passed_with_warnings",
          "summary": "検証対象がありません",
          "source": {"kind": "file", "workspaceId": "platform", "path": ".spec/bitz.yaml"}
        }
      ]
    },
    {
      "id": "web",
      "path": "apps/web",
      "status": "passed",
      "targetResults": [
        {
          "target": "web::REQ-001",
          "status": "passed",
          "contextDigest": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
          "statements": ["web::REQ-001:AC-01"],
          "bindingRefs": ["web::default"],
          "diagnostics": []
        }
      ],
      "commands": [
        {
          "bindingId": "web::default",
          "workspaceId": "web",
          "name": "default",
          "status": "passed",
          "termination": "exit",
          "cwd": ".",
          "argv": ["pytest", "-q", "tests/test_web.py"],
          "tests": ["tests/test_web.py"],
          "covers": ["web::REQ-001:AC-01"],
          "exitCode": 0,
          "timeoutSeconds": 300,
          "stdoutExcerpt": "1 passed",
          "stderrExcerpt": "",
          "stdoutTruncated": false,
          "stderrTruncated": false,
          "durationMs": 817
        }
      ],
      "durationMs": 842,
      "diagnostics": []
    }
  ],
  "revision": {"commit": "0123456789abcdef0123456789abcdef01234567", "dirty": false},
  "durationMs": 862,
  "diagnostics": []
}
```

### 2.3 doctor全体結果

```json
{
  "schemaVersion": "1.0",
  "operation": "doctor",
  "status": "passed",
  "federation": {"id": "platform", "path": "."},
  "core": {
    "version": "1.0.0",
    "apiVersion": "1.0",
    "capabilities": ["context.v1", "check.v1", "verify.v1", "doctor.v1", "monorepo.v1"]
  },
  "checks": [
    {"name": "git", "status": "passed"},
    {"name": "catalog", "status": "passed"}
  ],
  "workspaces": [
    {
      "id": "platform",
      "path": ".",
      "status": "passed",
      "checks": [{"name": "config", "status": "passed"}],
      "durationMs": 15,
      "diagnostics": []
    },
    {
      "id": "web",
      "path": "apps/web",
      "status": "passed",
      "checks": [{"name": "command", "status": "passed"}],
      "durationMs": 18,
      "diagnostics": []
    }
  ],
  "durationMs": 33,
  "diagnostics": []
}
```

global preflightがroot設定の構文、型、ID不正で停止し、有効なfederation IDを構成できない場合だけ、
`federation`を`{"id": null, "path": "."}`、`workspaces`を空配列にする。その他の全体結果の`federation.id`は
有効なstringとする。不正なraw IDを結果identityへ転記しない。

JSON consumerは`schemaVersion` majorを確認した後、次の排他的外形で結果種別を識別する。

- `workspace`を持ち、`federation`と`workspaces`を持たない: workspace単独結果
- `workspace`を持たず、`federation`と`workspaces`を持つ: 全体結果
- 両方を持つ、または必要fieldをどちらも持たない: Schema不適合

修飾IDの`::`、report file名、current directoryから結果種別を推測しない。連合producerを有効にするadapter／CIは、
事前にCore APIまたはdoctorで`monorepo.v1`を確認する。Coreは過去reportを合否入力にせず、単一と連合のreportを
同じ実行結果として集約しない。

## 3. statusと終了コード

| status | 意味 | 終了コード |
|---|---|---:|
| `passed` | 問題なし | 0 |
| `passed_with_warnings` | warningだけがある | 0 |
| `failed` | 入力成果物またはtest結果が不適合 | 1 |
| `blocked` | 前提不足または安全に継続不能 | 2 |
| `error` | tool、I/O、processの障害 | 3 |

CLI引数の構文不正、排他違反、未知option、解決不能な明示Git revision、構文上妥当でもcatalogにない
`--workspace`は終了コード4とし、Core操作結果とreportを生成しない。

終了コード4は操作statusでもDiagnosticでもなく、Core操作を開始しなかったことを表す。出力は
`--format`の指定にかかわらず次に固定する。

- 標準出力へ何も書かない。JSON本体、部分結果、空objectのいずれも返さない。
- 標準エラーへ理由を1行だけ書く。形式は`bitz: <operation-or-argv-context>: <reason>`とし、
  端末制御文字を無害化する。
- reportを作らず、既存reportを変更しない。

adapterとCIは終了コード4を、statusによる分岐の前に終了コードだけで判別する。標準エラーの文言は
人間向けであり、機械判定へ使用しない。

`info` Diagnosticはstatusを変更しない。warningだけなら`passed_with_warnings`とする。
複数結果は次の最悪値順で集約する。

```text
error > failed > blocked > passed_with_warnings > passed
```

最終statusだけで個別原因を隠さず、対象別結果とDiagnosticを保持する。Core 1.0はwarningをfailedへ昇格する
`--strict`を提供しない。

本表は操作statusとworkspace statusの語彙であり、Core全体で唯一とする。ただし`doctor`の`checks[]`は、
個別検査の結果に`info`と`warning`を加えた検査単位の語彙を使う。この語彙と操作statusへの集約規則は
[doctor仕様 §7](../03_操作仕様/04_doctor.md#7-結果)へ委譲する。他の操作は検査単位の語彙を持たない。

## 4. Diagnostic Schema

```json
{
  "code": "SPEC-RELATION-MISSING-001",
  "severity": "error",
  "resultStatus": "failed",
  "summary": "強い関係の参照先を解決できません",
  "source": {
    "kind": "file",
    "workspaceId": "root",
    "path": ".spec/requirements/REQ-001.md",
    "line": 8,
    "column": 5,
    "key": "relations.requires"
  },
  "specRefs": ["REQ-001"],
  "evidence": "TECH-999",
  "suggestedAction": "存在するIDへ修正してください"
}
```

必須fieldは`code`、`severity`、`resultStatus`、`summary`、`source`である。

| field | 型 | 必須 | 意味 |
|---|---|:--:|---|
| `code` | string | Yes | 永続的な機械識別子 |
| `severity` | enum | Yes | `info`、`warning`、`error`の表示優先度 |
| `resultStatus` | enum | Yes | このDiagnosticが操作結果へ与える効果 |
| `summary` | string | Yes | 人間向けの短い説明 |
| `source` | object | Yes | file、environment、invocationの判別可能なsource |
| `specRefs` | string[] | No | 関連SPECまたは規範文ID |
| `evidence` | string/object | No | 秘密を含まない最小根拠 |
| `suggestedAction` | string | No | 局所的な修正案 |
| `extensions` | object | No | 所有plugin固有情報 |

`severity`と操作statusは別軸である。例えば、error severityは成果物不適合の`failed`、前提不足の`blocked`、
tool障害の`error`のいずれにも対応できる。warningの`resultStatus`は`passed_with_warnings`、infoは`passed`を
原則とし、warningと`blocked`を組み合わせない。

## 5. source

| `kind` | 必須field | 任意field | 用途 |
|---|---|---|---|
| `file` | `workspaceId`、`path` | `line`、`column`、`key` | 設定、SPEC、code、test |
| `environment` | `component` | `identifier` | Core、実行環境、Git、command、cache、plugin |
| `invocation` | なし | `argument` | CLI引数またはadapterからの呼出し引数 |

単一workspaceの`file.workspaceId`は設定した実効IDを使う。連合では所有workspaceのIDを使い、`path`はそのworkspace相対、
`line`と`column`は1始まりとする。`workspaceId`と`path`の組でsourceを一意にし、絶対pathを返さない。

設定fileの構文、型またはroot ID不正によりworkspace identityをまだ構成できないDiagnosticだけは、必須field
`workspaceId`を`null`とする。この場合の`path`は発見済みworkspace候補相対で、root設定は`.spec/bitz.yaml`とする。
identity確定後のfile sourceと、設定以外のfile sourceに`null`を使わない。

## 6. Diagnostic code

codeは`<OWNER>-<AREA>-<NNN>`を基本とする。

| OWNER | 所有者 |
|---|---|
| `EAI` | EARS-AI言語 |
| `SPEC` | SPECモデルと操作 |
| `CTX` | Context解決とcontext操作 |

codeの再利用と意味変更を禁止する。廃止codeは予約済みとして一覧へ残すか、移行表で後継を示す。
同じ原因に対し、file単位と規範文単位の同義Diagnosticを重複して出さない。

relation edgeは構文・Schema、修飾ID、workspace、target、型の順に検査し、最初のprimary Diagnosticだけを返す。
strong target不在は`SPEC-RELATION-MISSING-001`へ統一し、`CTX-RELATION-MISSING-001`はCore 1.0で使用せず予約する。
詳細は[関係・トレースモデル](../02_SPECモデル/04_関係・トレースモデル.md#51-relation-diagnosticの優先順位)に従う。

### 6.1 Diagnostic表の閉包

公開Diagnostic条件の閉じた集合は[Diagnostic registry](05_Diagnostic-registry.md)だけが所有する。
各registry行は`conditionId`、返し得る操作、code、severity、`resultStatus`、source kind、継続単位、
primary優先順位を1つずつ持つ。各操作仕様とSPECモデル仕様のDiagnostic表は検索用索引であり、registryにないcodeや
条件を追加したり、registryの値を上書きしたりできない。

同じraw原因に複数条件が成立する場合はregistryのpriorityが最小の1行だけをprimary Diagnosticとして返す。
独立原因は別々に返し、共通のDiagnostic sort規則で並べる。予約済みcodeはregistryの予約表に残すが公開結果へ返さない。

`verify`のContext非成功はtargetの`diagnostics`へ置き、`bindingRefs`を空にする。global preflight、workspace、文書、
target、binding、doctor checkの停止・継続境界もregistryの`continuation`へ従う。

## 7. textとJSON

`--format`省略時の既定値はcontextが`markdown`、check、verify、doctorが`text`である。formatは表示だけを変え、
結果内容、status、終了コード、report内容を変えない。contextは`text`を提供せず、markdownまたはjsonだけを提供する。

- text出力はstatus、対象件数、scope、所要時間を1行で示す。
- `--format json`は同じ結果を標準出力へ返し、追加ファイルを生成しない。
- Diagnosticの順序はsource workspace ID、path、line、column、code、specRefsの辞書順とし、identity確定前の
  `workspaceId: null`はstring IDより前に置く。
- 端末制御文字を無害化する。
- textとJSONでstatus、件数、終了コードを変えない。

text出力は次の3部からなる。Diagnosticが0件なら要約行だけを出す。

```text
<operation> <status> scope=<scope> targets=<n> diagnostics=<n> (<duration>ms)
<workspace-id>:<path>:<line>:<column>: <severity>: <code>: <summary>
  -> <suggestedAction>
```

- 要約行は常に1行目とし、statusと件数をJSON結果と一致させる。doctorは`scope=`を出さない。
- Diagnostic行はJSONの`diagnostics`と同じ順序で1件1行とし、`source.kind`が`file`以外の場合は
  `<component>`または`invocation`を先頭fieldへ置く。`line`と`column`を持たない場合は当該fieldを省略せず空にする。
- `suggestedAction`を持つDiagnosticだけ、直後へ2 space字下げの継続行を1行出す。
- 全体操作ではworkspace要素のDiagnosticをworkspace処理順に続けて出し、top-level Diagnosticを先に置く。
  verifyのtarget固有Diagnosticは、所有するtop-levelまたはworkspaceのDiagnosticに続け、target ID順で出す。
- 色、装飾、進捗表示はCore 1.0の契約に含めない。

textはDiagnosticの`evidence`と`extensions`を出力しない。完全な機械可読情報は`--format json`を使う。

`targets=<n>`と`diagnostics=<n>`は次のJSON導出式へ固定し、表示側で別に数えない。

| operation／scope | `targets` |
|---|---:|
| check／`changed` | `selection.targetDocumentCount` |
| check／`selected`、`full` | `checkedDocumentCount` |
| check／`all-workspaces` | 全`workspaces[].checkedDocumentCount`の和 |
| verify／`selected`、`all` | `targetResults.length` |
| verify／`all-workspaces` | 全`workspaces[].targetResults.length`の和 |
| doctor workspace | `checks.length` |
| doctor federation | top-level `checks.length`と全`workspaces[].checks.length`の和 |

`diagnostics`は結果treeに実在するDiagnosticの総数である。top-level `diagnostics`、全`workspaces[].diagnostics`、
全`targetResults[].diagnostics`の長さを合計する。Diagnosticを複製して件数を合わせてはならない。

## 8. report

`check`と`verify`はstatusにかかわらず、`--report`が指定された場合だけ`.spec/reports/`へ結果JSONを保存する。
`--report`がなければ標準出力と終了コードだけを返し、既存reportを変更せず、新しいfileも作らない。
`--format json`は標準出力の形式だけを変え、保存を含意しない。引数不正、`context`、`doctor`はreportを保存しない。

workspace単独reportは対象workspace、全体reportはfederation rootの`.spec/reports/`へ保存する。
ファイル名は`.spec/reports/<YYYYMMDDTHHMMSSZ>-<operation>[-<sequence>].json`とする。同一秒の衝突は
安全な排他的作成と1以上の連番で回避する。保存失敗は`SPEC-REPORT-WRITE-001`／error／`error`とするが、
元の結果とDiagnosticは端末へ保持する。

reportへ環境変数値、秘密情報、stdout/stderr全文を含めない。reportは次回の合否判定への入力にしない。
