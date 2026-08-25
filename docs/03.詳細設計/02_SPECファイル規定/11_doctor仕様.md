# `bitz doctor`仕様 1.0

## 1. 目的

`bitz doctor`は、Coreと`.spec/`を利用できる前提が揃っているかを読取り専用で診断し、停止理由と
貼り付け可能な最小修復手順を返す。環境を自動変更せず、別のセットアップサービスを必要としない。

## 2. 公開操作

```text
bitz doctor [--format text|json]
```

ネットワーク、LLM、テスト実行、設定更新を行わない。検証コマンドは実行せず、実行ファイルと`cwd`の
解決可否だけを確認する。

## 3. 検査順序

| # | 検査 | 判定 |
|---:|---|---|
| 1 | CoreとPythonの対応版 | 起動不能・版不整合は`error` |
| 2 | `.spec/`と`bitz.yaml` | 不在・Schema不正は`blocked` |
| 3 | EARS-AI版互換性 | 未知majorは`blocked` |
| 4 | Git利用可否 | 不在はwarningとし、失われる保証を列挙 |
| 5 | `verify.commands`の実行ファイルと`cwd` | 未解決は`blocked` |
| 6 | キャッシュ | 破損時は無視して再構築可能ならwarning |
| 7 | 未解消の影響候補件数 | 0件以上を情報として表示 |

独立して検査できる項目は、先行項目が失敗しても可能な限り続行する。

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

## 6. JSON結果

```json
{
  "schemaVersion": "1.0",
  "operation": "doctor",
  "status": "passed_with_warnings",
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
| `SPEC-DOCTOR-WORKSPACE-001` | `.spec/`または`bitz.yaml`がない |
| `SPEC-DOCTOR-CONFIG-001` | `bitz.yaml`のSchemaが不正 |
| `SPEC-DOCTOR-EARS-001` | EARS-AI版に互換性がない |
| `SPEC-DOCTOR-GIT-001` | Gitを利用できず一部保証が失われる |
| `SPEC-DOCTOR-COMMAND-001` | 検証コマンドまたは`cwd`を解決できない |
| `SPEC-DOCTOR-CACHE-001` | キャッシュが破損または不整合 |
