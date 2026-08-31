# `bitz doctor`仕様 1.0

## 1. 目的

`bitz doctor`は、Coreと`.spec/`を利用できる前提が揃っているかを読取り専用で診断し、停止理由と
貼り付け可能な最小修復手順を返す。環境を自動変更せず、別のセットアップサービスを必要としない。

## 2. 公開操作

```text
bitz doctor [--workspace <workspace-id>|--all-workspaces] [--format text|json]
  [--plugin <id> --plugin-version <semver>]
  [--require-core-api <semver-range>]
  [--require-capability <capability-name>]...
```

ネットワーク、LLM、テスト実行、設定更新を行わない。検証コマンドは実行せず、実行ファイルと`cwd`の
解決可否だけを確認する。

MCPの`bitz_doctor`は同じ情報を構造化引数で受け取る。`plugin`を指定する場合、`pluginVersion`、
`requiredCoreApi`、`requiredCapabilities`を1つの要求として扱い、一部だけを暗黙補完しない。

## 3. 検査順序

| # | 検査 | 判定 |
|---:|---|---|
| 1 | Core実行体、MCP server、Pythonの対応版 | 起動不能・実行環境不適合は`error` |
| 2 | 呼出し元プラグインとCore API | major不一致・範囲外は`blocked` |
| 3 | 要求Capability | 1つでも不足すれば`blocked` |
| 4 | `.spec/`と`bitz.yaml`の存在 | 不在は`blocked` |
| 5 | `bitz.yaml`の構文、型、必須項目 | 不正は`error` |
| 6 | `schemaVersion`互換性 | 未知majorは`blocked` |
| 7 | モノレポ連合、member、workspace ID、所有境界 | 不整合は`blocked`または`failed` |
| 8 | EARS-AI版互換性 | 未知majorは`blocked` |
| 8a | `profiles`宣言 | Core 1.0では判定せず、宣言内容と未登録名前空間を情報として表示 |
| 9 | Git利用可否 | 不在はwarningとし、失われる保証を列挙 |
| 10 | `verify.commands`の実行ファイルと`cwd` | 未解決は`blocked` |
| 11 | キャッシュ | 破損時は無視して再構築可能ならwarning |
| 12 | 未解消の影響候補件数 | 0件以上を情報として表示 |

独立して検査できる項目は、先行項目が失敗しても可能な限り続行する。

### 3.1 プラグイン互換性

各拡張プラグインは、Skillまたはadapterの処理開始時に自身のID、版、要求Core API範囲、要求Capabilityを
渡す。`doctor`はCoreが公開する実値と比較し、Skillの自然言語判断へ委ねない。初回利用、セッション再開、
プラグインまたはCoreの版変更後に必須とし、同一セッションの全ツール呼出し前には繰り返さない。

Capability名は`context.v1`、`check.v1`、`verify.v1`、`doctor.v1`、`monorepo.v1`のように、操作名とAPI majorを
ピリオドで連結する。未知Capabilityは不足として扱う。Core API minor差は、要求範囲と全Capabilityを
満たす場合だけ許可する。

Agent Plugins 1.0には導入済みプラグインを横断列挙する標準APIがないため、`doctor`はクライアント固有の
インストール先を探索しない。`.spec/bitz.yaml`も導入済みプラグイン台帳として扱わない。呼出し元から
プラグイン情報が渡されない通常の`bitz doctor`は、Coreとワークスペースだけを診断する。

### 3.2 モノレポ連合

通常の`doctor`はactive workspaceと、そこから解決に必要な連合カタログを診断する。
`doctor --all-workspaces`は連合ルートでだけ使用し、全memberの設定、workspace ID、path、Schema/EARS-AI major、
所有境界、検証コマンドを読取り専用で検査する。未登録の`.spec/`を自動的にmemberへ追加しない。

## 4. 初回導入

`.spec/`または`bitz.yaml`がない場合は`SPEC-DOCTOR-WORKSPACE-001`と`blocked`を返し、作成先と
次の最小設定を`suggestedAction`へ含める。

```yaml
schemaVersion: "1.0"
language: ja
earsAi: "1.0"
```

さらに`.gitignore`へ`.spec/reports/`を追加する提案と、次に実行する`bitz check --full`を表示する。
`doctor`自身はディレクトリ、設定、`.gitignore`を作成しない。

## 5. Git不在時

Git不在はCore全体の起動失敗にしない。構文、Schema、参照、Context、テスト実行は利用できるが、承認済み
要求の差分保護とTASK変更境界を保証できないことを明示する。縮退の正は
[更新・互換性・安全性](07_更新・互換性・安全性.md) §8とする。
ただしモノレポ連合ではGitルート、member境界、所有範囲を確定できないため、連合操作を`blocked`とする。

## 6. JSON結果

```json
{
  "schemaVersion": "1.0",
  "operation": "doctor",
  "status": "passed_with_warnings",
  "workspace": {"id": "web", "path": "apps/web"},
  "core": {
    "version": "1.3.0",
    "apiVersion": "1.0",
    "capabilities": ["context.v1", "check.v1", "verify.v1", "doctor.v1", "monorepo.v1"]
  },
  "plugin": {
    "id": "bitz-sdd",
    "version": "1.2.0",
    "compatibility": "compatible"
  },
  "checks": [
    {"name": "core-version", "status": "ok"},
    {"name": "git", "status": "warning", "lostGuarantees": ["approved-diff-protection", "task-boundary"]}
  ],
  "diagnostics": []
}
```

集約statusは`error`、`failed`、`blocked`、`passed_with_warnings`、`passed`の順で最も悪い状態を採用する。

## 7. Diagnostic

| コード | 条件 |
|---|---|
| `SPEC-DOCTOR-CORE-001` | CoreまたはPythonの版が不適合 |
| `SPEC-DOCTOR-PLUGIN-001` | プラグインID、版、互換性要求が不正または不足 |
| `SPEC-DOCTOR-API-001` | 要求Core API範囲と実行中Coreが非互換 |
| `SPEC-DOCTOR-CAPABILITY-001` | 要求CapabilityをCoreが提供しない |
| `SPEC-DOCTOR-WORKSPACE-001` | `.spec/`または`bitz.yaml`がない |
| `SPEC-DOCTOR-CONFIG-001` | `bitz.yaml`のSchemaが不正 |
| `SPEC-DOCTOR-EARS-001` | `earsAi`のmajorに互換性がない。Core 1.0では`profiles`をこの判定へ含めない |
| `SPEC-DOCTOR-GIT-001` | Gitを利用できず一部保証が失われる |
| `SPEC-DOCTOR-COMMAND-001` | 検証コマンドまたは`cwd`を解決できない |
| `SPEC-DOCTOR-CACHE-001` | キャッシュが破損または不整合 |

モノレポ構造のDiagnosticは[モノレポSPEC連合仕様](12_モノレポSPEC連合仕様.md) §10を使用し、`doctor`専用の
同義コードを重複定義しない。

Core自体が未導入またはMCP serverが起動せず`doctor`を呼べない場合、この診断形式は生成できない。
拡張プラグインはその場合だけ静的な`bitz-core`導入手順を示して`blocked`とし、Coreの解析・判定を代替しない。
