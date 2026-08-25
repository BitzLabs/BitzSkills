# `bitz.yaml`仕様 1.0

## 1. 役割

`.spec/bitz.yaml`はワークスペースごとに1つだけ置く設定の正本である。Git管理を前提とし、
SPEC本文、環境変数、ユーザーのホームディレクトリにある設定から安全性や検証コマンドを上書きしない。

## 2. 最小例

```yaml
schemaVersion: "1.0"
language: ja
earsAi: "1.0"
check:
  changedOnly: true
context:
  maxDocuments: 20
  maxBytes: 131072
verify:
  timeoutSeconds: 300
  commands:
    default:
      - pytest
      - -q
      - "{tests}"
safety:
  protectApprovedRequirements: true
```

## 3. Schema

| キー | 型 | 必須 | 既定値 | 制約 |
|---|---|:--:|---|---|
| `schemaVersion` | string | Yes | なし | Core 1.0では`"1.0"` |
| `language` | string | No | `ja` | BCP 47の言語タグ |
| `earsAi` | string | Yes | なし | 対象EARS-AIのmajor.minor |
| `check.changedOnly` | boolean | No | `true` | 通常検査の範囲 |
| `context.maxDocuments` | integer | No | `20` | 1以上100以下 |
| `context.maxBytes` | integer | No | `131072` | 4096以上1048576以下 |
| `verify.timeoutSeconds` | integer | No | `300` | 1以上3600以下 |
| `verify.commands` | map | No | `{}` | コマンド名からargvへの対応 |
| `safety.protectApprovedRequirements` | boolean | No | `true` | 承認済み要求の意味変更を検出 |

未知の標準キーは、同じmajor内の前方互換性のため警告して保持する。型不正、必須キー欠如、
未知の`schemaVersion` majorはエラーとする。

`verify.commands`は仕様作成だけの段階では省略できる。`bitz verify`を実行するときに対象のコマンドが
定義されていなければ`blocked`とする。

Contextの上限は完全な依存閉包を部分的に切り捨てるためではない。上限を超えた場合は`blocked`とし、
利用者が依存の分割またはhard limit内での明示的な上限変更を判断する。

## 4. 検証コマンド

`verify.commands`のキーは`[a-z][a-z0-9-]{0,31}`とし、値は空でない文字列配列とする。
先頭要素は実行ファイル、残りは引数である。Coreはシェルを介さずargvとして起動する。

```yaml
verify:
  commands:
    default: [pytest, -q, "{tests}"]
    frontend: [npm, test, "--", "{tests}"]
```

`{tests}`は配列要素全体として1回だけ使用でき、対象要求の`tests`を1パスずつのargvへ展開する。
文字列の一部への埋込み、環境変数展開、コマンド置換、パイプ、リダイレクトは行わない。
`{tests}`がなければ設定されたargvをそのまま1回実行する。

実行ファイルはPATHから解決する。SPEC文書のFrontmatterや本文は、コマンド、引数、環境変数、
作業ディレクトリを定義できない。

## 5. 実効設定

コマンドライン引数は対象範囲、出力形式、レポート生成、タイムアウト短縮だけを変更できる。
タイムアウト延長、保護解除、検証コマンド差替えは行わない。

`bitz check --format json`と`bitz doctor --format json`は、秘密情報を含まない実効設定を結果へ含めてよい。
Core 1.0は`.env`を読み込まず、設定値の文字列補間を行わない。

## 6. 解析制約

- UTF-8のYAML 1.2 subsetとして解析する。
- カスタムタグ、アンカー、エイリアス、merge keyを禁止する。
- 重複キーをエラーとする。
- ファイルサイズ上限を64 KiBとする。
- Parserはネットワークアクセスを行わない。
