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
| `workspace` | object | Yes | Core 1.0では`{"id":"root","path":"."}` |
| `revision` | object/null | 操作依存 | Git基準版と実行時状態 |
| `durationMs` | integer | Yes | 非負の経過ms |
| `diagnostics` | array | Yes | 0件以上のDiagnostic |

未知の同一major内fieldは保持または無視できる。未知majorは`blocked`として処理を続けない。

## 3. statusと終了コード

| status | 意味 | 終了コード |
|---|---|---:|
| `passed` | 問題なし | 0 |
| `passed_with_warnings` | warningだけがある | 0 |
| `failed` | 入力成果物またはtest結果が不適合 | 1 |
| `blocked` | 前提不足または安全に継続不能 | 2 |
| `error` | tool、I/O、processの障害 | 3 |

CLI引数の構文不正、排他違反、解決不能な明示Git revisionは終了コード4とし、workspace結果を生成しない。

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

Core 1.0の`file.workspaceId`は常に`root`、`path`はworkspace相対、`line`と`column`は1始まりとする。
絶対pathを返さない。

## 6. Diagnostic code

codeは`<OWNER>-<AREA>-<NNN>`を基本とする。

| OWNER | 所有者 |
|---|---|
| `EAI` | EARS-AI言語 |
| `SPEC` | SPECモデルと操作 |
| `CTX` | Context解決とcontext操作 |

codeの再利用と意味変更を禁止する。廃止codeは予約済みとして一覧へ残すか、移行表で後継を示す。
同じ原因に対し、file単位と規範文単位の同義Diagnosticを重複して出さない。

## 7. textとJSON

- text出力は成功時にstatus、対象件数、scope、所要時間を1行で示す。
- `--format json`は同じ結果を標準出力へ返し、追加ファイルを生成しない。
- Diagnosticの順序はsource path、line、column、code、specRefsの辞書順とする。
- 端末制御文字を無害化する。
- textとJSONでstatus、件数、終了コードを変えない。

## 8. report

`check`と`verify`は次の場合だけ`.spec/reports/`へ結果JSONを保存する。

- `--report`が指定された
- statusが`failed`、`blocked`、`error`である

`passed`と`passed_with_warnings`は`--report`指定時だけ保存する。引数不正は保存しない。
`context`と`doctor`はCore 1.0ではreportを保存しない。

ファイル名は`.spec/reports/<YYYYMMDDTHHMMSSZ>-<operation>[-<sequence>].json`とする。同一秒の衝突は
安全な排他的作成と1以上の連番で回避する。保存失敗は`SPEC-REPORT-WRITE-001`／error／`error`とするが、
元の結果とDiagnosticは端末へ保持する。

reportへ環境変数値、秘密情報、stdout/stderr全文を含めない。reportは次回の合否判定への入力にしない。
