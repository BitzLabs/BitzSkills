# `bitz doctor`仕様 1.0

## 1. 目的

Coreと`.spec/`を利用できる前提を読取り専用で診断し、停止理由と貼付け可能な最小修復手順を返す。
環境を自動変更せず、network、LLM、test実行を行わない。

## 2. 公開操作

```text
bitz doctor [--format text|json]
  [--workspace <workspace-id>|--all-workspaces]
  [--plugin <id> --plugin-version <semver>]
  [--require-core-api <semver-range>]
  [--require-capability <capability-name>]...
```

plugin情報を指定する場合はID、version、required API、capabilityを1つの要求として扱い、一部を暗黙補完しない。

## 3. 検査順序

| # | 検査 | 不適合 |
|---:|---|---|
| 1 | Core実行体、Python version、起動 | version不適合はblocked、起動障害はerror |
| 2 | 呼出しpluginとCore API | blocked |
| 3 | required Capability | blocked |
| 4 | `.spec/bitz.yaml`存在 | blocked |
| 5 | 設定構文、型、必須field | error |
| 6 | 連合catalog、member、path所有 | failed／blocked |
| 7 | Schema major | blocked |
| 8 | EARS-AI major | blocked |
| 9 | Git利用可否 | 単一はwarning、連合はblocked |
| 10 | command実行fileとcwd | blocked |
| 11 | cache | 再構築可能ならwarning |
| 12 | 影響候補件数 | info |

独立検査は先行失敗後も可能な範囲で続行する。`--workspace`は選択member、`--all-workspaces`は同じGit rootと
federation rootを探索起点から一意に発見できる場合にcatalogと全memberをworkspace ID順に診断する。current directoryの
root一致は要求しない。Core 1.0はProfile互換性を検査しない。
`--all-workspaces`ではCore、plugin、Capability、Git、catalogをtop-levelで1回検査し、workspace固有の設定、版、
command、cwd、cache、影響候補を各member結果へ置く。同じ環境Diagnosticをmemberごとに複製しない。

全体診断はHEADと現在snapshotのGit既知`.spec/bitz.yaml`を、連合を宣言している各snapshot自身のcatalogと比較する。
unborn repositoryと連合化前の単一workspace HEADでは現在snapshotだけを連合完全性の対象にする。catalog、ID、path、
Git境界、未対応major、resource上限のglobal preflightが非成功ならmember診断を開始しない。

preflight通過後はcheck項目を継続単位とする。先行checkの出力を必要としないCore、plugin、Capability、Git、cacheは
可能な範囲で継続し、設定を解釈できないときのcommand／cwdなど依存checkは実行しない。根本Diagnosticとは別の
checkが依存出力不足だけで実行不能なら`SPEC-MONOREPO-DEPENDENCY-001`／blockedとし、同じcheckへ具体的原因を
重複させない。

## 4. Capability

Core 1.0は`context.v1`、`check.v1`、`verify.v1`、`doctor.v1`、`monorepo.v1`を公開する。未知Capabilityは不足とする。
Core API minor差は要求rangeと全Capabilityを満たす場合だけ許可する。

doctorはclient固有plugin install先を探索せず、`bitz.yaml`をplugin台帳にしない。plugin情報が渡されない通常実行は
Coreとworkspaceだけを診断する。

## 5. 初回導入

設定不在は`SPEC-DOCTOR-WORKSPACE-001`／blockedとし、作成先と次をsuggestedActionへ含める。

```yaml
schemaVersion: "1.0"
language: ja
earsAi: "1.0"
```

`.gitignore`への`.spec/reports/`追加と、次の`bitz check --full`を提示する。doctor自身はfileを作らない。

## 6. Git不在

単一workspaceではCore全体の起動失敗にはせず、承認済みREQ保護、状態遷移、削除検出、TASK境界の失われる
保証を列挙する。連合ではrepository境界と所有範囲を確定できないため`SPEC-MONOREPO-GIT-001`／blockedとする。

## 7. 結果

```json
{
  "schemaVersion": "1.0",
  "operation": "doctor",
  "status": "passed_with_warnings",
  "workspace": {"id": "root", "path": "."},
  "core": {
    "version": "1.0.0",
    "apiVersion": "1.0",
    "capabilities": ["context.v1", "check.v1", "verify.v1", "doctor.v1", "monorepo.v1"]
  },
  "checks": [
    {"name": "git", "status": "warning", "lostGuarantees": ["approved-diff-protection", "task-boundary"]}
  ],
  "durationMs": 31,
  "diagnostics": []
}
```

`--all-workspaces`結果はtop-levelに`core`とglobal `checks[]`を持ち、各workspace結果は0件でも省略しない
workspace固有`checks[]`を持つ。同じCore／plugin／Capability／Git／catalog診断をmemberへ複製しない。

| `checks[]` field | 型 | 必須 | 意味 |
|---|---|:--:|---|
| `name` | string | Yes | 安定した検査名 |
| `status` | enum | Yes | `passed`、`info`、`warning`、`failed`、`blocked`、`error` |
| `lostGuarantees` | string[] | No | 縮退で失われる保証。重複なし辞書順 |

check statusの`info`は操作statusを変えず、`warning`は`passed_with_warnings`として集約する。`failed`、`blocked`、
`error`は同名の操作statusとして共通の最悪値規則へ加える。

単一workspaceではtop-level `checks[]`にglobalとworkspace固有検査を処理順で置く。全体結果ではglobal検査をtop-level、
workspace固有検査を該当workspace要素へ置く。完全JSON例は
[共通結果契約](../00_共通契約/01_結果・Diagnostic・終了コード.md#23-doctor全体結果)を正とする。

## 8. Diagnostic

| code | result | 条件 |
|---|---|---|
| `SPEC-DOCTOR-CORE-001` | blocked | Core/Python version不適合 |
| `SPEC-DOCTOR-CORE-002` | error | Core/MCP起動不能 |
| `SPEC-DOCTOR-PLUGIN-001` | failed | plugin要求形式不正 |
| `SPEC-DOCTOR-API-001` | blocked | API非互換 |
| `SPEC-DOCTOR-CAPABILITY-001` | blocked | Capability不足 |
| `SPEC-DOCTOR-WORKSPACE-001` | blocked | `.spec/bitz.yaml`不在 |
| `SPEC-DOCTOR-CONFIG-001` | error | 設定構文・型・必須field不正 |
| `SPEC-DOCTOR-EARS-001` | blocked | EARS-AI major非互換 |
| `SPEC-DOCTOR-GIT-001` | passed_with_warnings | Git不在 |
| `SPEC-DOCTOR-COMMAND-001` | blocked | command/cwd解決不能 |
| `SPEC-DOCTOR-CACHE-001` | passed_with_warnings | cache不整合だが再構築可能 |
| `SPEC-MONOREPO-DEPENDENCY-001` | blocked | 先行する別unitの出力不足でworkspace固有checkを実行不能 |

Core自体が未導入でdoctorを呼べない場合、adapterは静的な導入手順だけを示し、Core判定を代替しない。
連合固有Diagnosticと全体結果外形は
[モノレポSPEC連合仕様](../02_SPECモデル/05_モノレポSPEC連合仕様.md)に従う。
