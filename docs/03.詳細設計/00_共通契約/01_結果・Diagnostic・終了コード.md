# 結果・Diagnostic・終了コード

## 1. 所有範囲

本書は全Core操作が共有する結果外形、status、Diagnostic、終了コード、report生成条件を定義する。
操作固有fieldとDiagnostic条件は各操作仕様が定義するが、共通fieldの意味と集約を再定義しない。

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
  "durationMs": 184,
  "diagnostics": []
}
```

| field | 型 | 必須 | 意味 |
|---|---|:--:|---|
| `schemaVersion` | string | Yes | 結果Schema major.minor |
| `operation` | enum | Yes | `context`、`check`、`verify`、`doctor` |
| `status` | enum | Yes | 操作全体のstatus |
| `scope` | string | 操作依存 | 対象範囲 |
| `workspace` | object | workspace単独操作 | 対象またはrequest workspaceの`id`と`path`。単一は`.`、連合内はrepository root相対 |
| `federation` | object | 全体操作 | federation rootの`id`と`path: "."`。root identity不成立時だけ`id: null` |
| `workspaces` | array | 全体操作 | 処理順のworkspace別結果。操作固有fieldを保持 |
| `revision` | object/null | 操作依存 | Git基準版と実行時状態 |
| `durationMs` | integer | Yes | 非負の経過ms |
| `diagnostics` | array | Yes | 0件以上のDiagnostic |

未知の同一major内fieldは保持または無視できる。未知majorは`blocked`として処理を続けない。

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

CLI引数の構文不正、排他違反、解決不能な明示Git revision、構文上妥当でもcatalogにない`--workspace`は
終了コード4とし、Core操作結果とreportを生成しない。

`info` Diagnosticはstatusを変更しない。warningだけなら`passed_with_warnings`とする。
複数結果は次の最悪値順で集約する。

```text
error > failed > blocked > passed_with_warnings > passed
```

最終statusだけで個別原因を隠さず、対象別結果とDiagnosticを保持する。Core 1.0はwarningをfailedへ昇格する
`--strict`を提供しない。

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
| `environment` | `component` | `identifier` | Core、Python、Git、command、cache、plugin |
| `invocation` | なし | `argument` | CLI/MCP呼出し |

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

## 7. textとJSON

- text出力は成功時にstatus、対象件数、scope、所要時間を1行で示す。
- `--format json`は同じ結果を標準出力へ返し、追加ファイルを生成しない。
- Diagnosticの順序はsource workspace ID、path、line、column、code、specRefsの辞書順とし、identity確定前の
  `workspaceId: null`はstring IDより前に置く。
- 端末制御文字を無害化する。
- textとJSONでstatus、件数、終了コードを変えない。

## 8. report

`check`と`verify`はstatusにかかわらず、`--report`が指定された場合だけ`.spec/reports/`へ結果JSONを保存する。
`--report`がなければ標準出力と終了コードだけを返し、既存reportを変更せず、新しいfileも作らない。
`--format json`は標準出力の形式だけを変え、保存を含意しない。引数不正、`context`、`doctor`はreportを保存しない。

workspace単独reportは対象workspace、全体reportはfederation rootの`.spec/reports/`へ保存する。
ファイル名は`.spec/reports/<YYYYMMDDTHHMMSSZ>-<operation>[-<sequence>].json`とする。同一秒の衝突は
安全な排他的作成と1以上の連番で回避する。保存失敗は`SPEC-REPORT-WRITE-001`／error／`error`とするが、
元の結果とDiagnosticは端末へ保持する。

reportへ環境変数値、秘密情報、stdout/stderr全文を含めない。reportは次回の合否判定への入力にしない。
