# `bitz doctor`仕様 1.0

## 1. 目的

Coreと`.spec/`を利用できる前提を読取り専用で診断し、停止理由と貼付け可能な最小修復手順を返す。
環境を自動変更せず、network、LLM、test実行を行わない。

## 2. 公開操作

```text
bitz doctor [--format text|json]
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
| 6 | Schema major | blocked |
| 7 | EARS-AI major | blocked |
| 8 | Git利用可否 | warning |
| 9 | command実行fileとcwd | blocked |
| 10 | cache | 再構築可能ならwarning |
| 11 | 影響候補件数 | info |

独立検査は先行失敗後も可能な範囲で続行する。Core 1.0はProfile互換性、モノレポmember、
`monorepo.v1` Capabilityを検査しない。

## 4. Capability

Core 1.0は`context.v1`、`check.v1`、`verify.v1`、`doctor.v1`を公開する。未知Capabilityは不足とする。
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

Core全体の起動失敗にはしない。構文、関係、Context、明示check、test実行は利用できるが、承認済みREQ保護、
状態遷移、削除検出、TASK境界の失われる保証を列挙する。

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
    "capabilities": ["context.v1", "check.v1", "verify.v1", "doctor.v1"]
  },
  "checks": [
    {"name": "git", "status": "warning", "lostGuarantees": ["approved-diff-protection", "task-boundary"]}
  ],
  "diagnostics": []
}
```

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

Core自体が未導入でdoctorを呼べない場合、adapterは静的な導入手順だけを示し、Core判定を代替しない。
