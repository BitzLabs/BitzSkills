# `bitz doctor`仕様 1.0

## 1. 目的

Coreと`.spec/`を利用できる前提を読取り専用で診断し、停止した理由と貼付け可能な最小の修復手順を返す。
環境を自動で変更せず、ネットワーク、LLM、テストの実行を行わない。

## 2. 公開操作

```text
bitz doctor [--format text|json]
  [--workspace <workspace-id>|--all-workspaces]
  [--plugin <id> --plugin-version <semver>]
  [--require-core-api <semver-range>]
  [--require-capability <capability-name>]...
```

引数列の共通の解析、オプションの重複、空の値、実行環境は
[Core実行環境・CLI基盤契約](../00_共通契約/06_Core実行環境・CLI基盤契約.md)に従う。
プラグインの情報を指定する場合は、ID、バージョン、要求するAPI、対応機能（Capability）を1つの要求として扱い、一部を暗黙に補わない。
`--format`の既定値は`text`である。

## 3. 検査順序

| # | 検査 | 不適合 |
|---:|---|---|
| 1 | Coreの実行体、実行環境のバージョン、起動 | 下限未満は`blocked`、起動の障害は`error` |
| 2 | 呼び出したプラグインとCore API | `blocked` |
| 3 | 要求する対応機能 | `blocked` |
| 4 | `.spec/bitz.yaml`の存在 | `blocked` |
| 5 | 設定の構文、型、必須フィールド | `SPEC-CONFIG-SCHEMA-001`／`error` |
| 6 | 複合ワークスペースのカタログ、メンバー、パスの所有 | `failed`／`blocked` |
| 7 | スキーマのメジャーバージョン | `blocked` |
| 8 | EARS-AIのメジャーバージョン | `blocked` |
| 9 | Gitの利用可否と下限のバージョン | 単一ワークスペースは`warning`、複合ワークスペースは`blocked` |
| 10 | コマンドの実行ファイルと`cwd` | `blocked` |
| 11 | 影響候補の件数 | `info` |

独立した検査は、先行する失敗の後も可能な範囲で継続する。`--workspace`は選択したメンバー、`--all-workspaces`は同じGitのリポジトリの
ルートとルートワークスペースを探索の開始位置から一意に発見できる場合に、カタログとすべてのメンバーをワークスペースIDの順で診断する。
現在のディレクトリがルートと一致することは要求しない。Core 1.0はプロファイルの互換性を検査しない。
`--all-workspaces`では、Core、プラグイン、対応機能、Git、カタログを最上位で1回検査し、ワークスペース固有の設定、バージョン、
コマンド、`cwd`、影響候補を各メンバーの結果へ置く。同じ環境の診断をメンバーごとに複製しない。

`--all-workspaces`の`doctor`は`HEAD`と現在のスナップショットのGitが認識している`.spec/bitz.yaml`を、複合ワークスペースを宣言している各スナップショット自身のカタログと比較する。
コミットのないリポジトリと、複合ワークスペース化の前の単一ワークスペースの`HEAD`では、現在のスナップショットだけを複合ワークスペースの完全性の対象にする。カタログ、ID、パス、
Gitの境界、非対応のメジャーバージョン、リソースの上限の全体事前検査が非成功ならメンバーの診断を開始しない。

事前検査を通過した後は、検査項目（check）を継続単位とする。先行する検査項目の出力を必要としないCore、プラグイン、対応機能、Gitは
可能な範囲で継続し、設定を解釈できないときのコマンドや作業ディレクトリの検査項目など、依存する検査項目は実行しない。根本の診断とは別の
検査項目が、依存する出力の不足だけで実行不能なら、診断`SPEC-MULTI-DEPENDENCY-001`（`blocked`）とし、同じ検査項目へ具体的な原因を
重複させない。

### 3.1 実行環境の下限

検査1は次の下限と比較する。値は
[Core実行環境・CLI基盤契約 §2・§4](../00_共通契約/06_Core実行環境・CLI基盤契約.md#2-実行環境と配布物)が所有する。

| 対象 | 下限 | 不適合時 |
|---|---|---|
| CPython | 3.12 | `SPEC-DOCTOR-CORE-001`／`blocked` |
| Git | 2.30 | Git不在として扱い、単一ワークスペースは`warning`、複合ワークスペースは`SPEC-MULTI-GIT-001`／`blocked` |

下限は環境ごとに変更できる設定値にしない。Core実行体を起動できない場合は
`SPEC-DOCTOR-CORE-002`／`error`とし、バージョンの比較へ進まない。

## 4. 対応機能

Core 1.0は`context.v1`、`check.v1`、`verify.v1`、`doctor.v1`、`multiWorkspace.v1`を公開する。未知の対応機能は不足として扱う。
Core APIのマイナーバージョンの差は、要求する範囲とすべての対応機能を満たす場合だけ許可する。

`doctor`はクライアント固有のプラグインのインストール先を探索せず、`bitz.yaml`をプラグインの台帳にしない。プラグインの情報が渡されない通常の実行は
Coreとワークスペースだけを診断する。

## 5. 初回導入

設定の不在は診断`SPEC-DOCTOR-WORKSPACE-001`（`blocked`）とし、作成先と次を`suggestedAction`へ含める。

```yaml
schemaVersion: "1.0"
language: ja
earsAi: "1.0"
```

`.gitignore`への`.spec/reports/`の追加と、次に行う`bitz check --full`を提示する。`doctor`自身はファイルを作らない。

## 6. Git不在

単一ワークスペースでは、Core全体の起動の失敗にはせず、承認済み要求の保護、状態遷移、削除の検出、TASK境界の失われる
保証を列挙する。`checks[]`の`git`は、この4件を`lostGuarantees`へ`approved-diff-protection`、
`deletion-detection`、`status-transition`、`task-boundary`の安定した名前で重複なく辞書順に置く。
複合ワークスペースでは、リポジトリの境界と所有領域を確定できないため診断`SPEC-MULTI-GIT-001`（`blocked`）とする。

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
    "capabilities": ["context.v1", "check.v1", "verify.v1", "doctor.v1", "multiWorkspace.v1"]
  },
  "checks": [
    {"name": "git", "status": "warning", "lostGuarantees": ["approved-diff-protection", "task-boundary"]}
  ],
  "durationMs": 31,
  "diagnostics": []
}
```

`--all-workspaces`の結果は、最上位に`core`とワークスペースに依存しない`checks[]`を持ち、各ワークスペースの結果は0件でも省略しない
ワークスペース固有の`checks[]`を持つ。同じCore、プラグイン、対応機能、Git、カタログの診断をメンバーへ複製しない。

`core`はすべての`doctor`の結果で必須とする。Core実行体を観測できない`SPEC-DOCTOR-CORE-002`の場合だけ`version`と
`apiVersion`を`null`、`capabilities`を空配列にする。それ以外は観測した文字列値と対応機能の配列を返す。

| `checks[]`のフィールド | 型 | 必須 | 内容 |
|---|---|:--:|---|
| `name` | 文字列 | ○ | 安定した検査の名前 |
| `status` | 列挙値 | ○ | `passed`、`info`、`warning`、`failed`、`blocked`、`error` |
| `lostGuarantees` | 文字列の配列 | — | 縮退で失われる保証。重複のない辞書順 |

検査項目の状態の`info`は操作の状態を変えず、`warning`は`passed_with_warnings`として集約する。`failed`、`blocked`、
`error`は同名の操作の状態として共通の最悪値の規則へ加える。

単一ワークスペースでは、最上位の`checks[]`にワークスペースに依存しない検査とワークスペース固有の検査を処理順で置く。全体結果ではワークスペースに依存しない検査を最上位、
ワークスペース固有の検査を該当するワークスペースの要素へ置く。完全なJSONの例は
[共通結果契約](../00_共通契約/01_結果・診断・終了コード.md#23-doctorの全体結果)を正とする。

## 8. 診断

| 診断コード | 結果 | 条件 |
|---|---|---|
| `SPEC-DOCTOR-CORE-001` | `blocked` | 実行環境のバージョンが下限未満 |
| `SPEC-DOCTOR-CORE-002` | `error` | Core実行体を起動できない |
| `SPEC-DOCTOR-PLUGIN-001` | `failed` | プラグインの要求の形式が不正 |
| `SPEC-DOCTOR-API-001` | `blocked` | APIが非互換 |
| `SPEC-DOCTOR-CAPABILITY-001` | `blocked` | 対応機能が不足 |
| `SPEC-DOCTOR-WORKSPACE-001` | `blocked` | `.spec/bitz.yaml`が不在 |
| `SPEC-DOCTOR-EARS-001` | `blocked` | EARS-AIのメジャーバージョンが非互換 |
| `SPEC-DOCTOR-GIT-001` | `passed_with_warnings` | Git不在 |
| `SPEC-DOCTOR-COMMAND-001` | `blocked` | コマンドの実行ファイルまたは作業ディレクトリを解決できない |
| `SPEC-MULTI-DEPENDENCY-001` | `blocked` | 先行する別の単位の出力の不足でワークスペース固有の検査項目を実行できない |

Core自体が未導入で`doctor`を呼べない場合、アダプターは静的な導入手順だけを示し、Coreによる判定を代替しない。
複合ワークスペース固有の診断と全体結果の外形は
[複合ワークスペース仕様](../02_仕様文書モデル/05_複合ワークスペース仕様.md)に従う。

設定の不適合は`SPEC-CONFIG-SCHEMA-001`だけを診断へ置き、`doctor`の設定の検査項目がその診断を参照する。
`SPEC-DOCTOR-CONFIG-001`と`SPEC-DOCTOR-CACHE-001`は予約済みとし、公開結果へ返さない。Core 1.0は永続的なキャッシュを
持たないため、キャッシュの検査を行わない。すべての条件の診断コード、重大度、結果への効果、発生元、継続単位は
[診断レジストリ](../00_共通契約/05_診断レジストリ.md)が所有する。
`doctor`はレポートを保存しないため`SPEC-REPORT-WRITE-001`を返さない。
