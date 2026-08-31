# `bitz.yaml`仕様 1.0

## 1. 役割

`.spec/bitz.yaml`はワークスペースごとに1つだけ置く設定の正本である。Git管理を前提とし、
SPEC本文、環境変数、ユーザーのホームディレクトリにある設定から安全性や検証コマンドを上書きしない。
モノレポではGitルートの設定だけが連合カタログを持ち、member設定は継承せず自己完結する。

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

モノレポ連合ルートでは次を追加する。

```yaml
workspace:
  id: platform
monorepo:
  maxMembers: 20
  members:
    - id: web
      path: apps/web
    - id: api
      path: services/api
```

## 3. Schema

| キー | 型 | 必須 | 既定値 | 制約 |
|---|---|:--:|---|---|
| `schemaVersion` | string | Yes | なし | Core 1.0では`"1.0"` |
| `language` | string | No | `ja` | BCP 47の言語タグ |
| `earsAi` | string | Yes | なし | 対象EARS-AIのmajor.minor |
| `profiles` | map | No | `{}` | Profile名前空間から`major.minor`への対応。Core 1.0では保持のみ |
| `workspace.id` | string | No | `root` | workspace識別子。連合ルートとmemberでは必須 |
| `monorepo.members` | object[] | No | なし | Gitルートだけで使用する`id`と`path`の明示カタログ |
| `monorepo.maxMembers` | integer | No | `20` | 1以上100以下。member数が超えれば`blocked` |
| `check.changedOnly` | boolean | No | `true` | 通常検査の範囲 |
| `context.maxDocuments` | integer | No | `20` | 1以上100以下 |
| `context.maxBytes` | integer | No | `131072` | 4096以上1048576以下 |
| `verify.timeoutSeconds` | integer | No | `300` | 1以上3600以下 |
| `verify.commands` | map | No | `{}` | コマンド名からargvと任意cwdへの対応 |
| `safety.protectApprovedRequirements` | boolean | No | `true` | 承認済み要求の意味変更を検出 |

未知の標準キーは、同じmajor内の前方互換性のため警告して保持する。型不正と必須キー欠如は`error`、
未知の`schemaVersion` majorは未対応の前提として`blocked`とする。

`profiles`はProfileの正式実装まで予約キーとする。Core 1.0は値の型（`map<string, string>`、
キーは`[a-z][a-z0-9]{0,15}`、値は`major.minor`）だけを検査し、未知キー警告を出さず、
合否判定、Context Digest、Projectionへ使用しない。Coreへ登録されていない名前空間の宣言は
`bitz doctor`が情報として表示する。Profile版の互換性判定は、当該Profileが正式実装された
時点で有効化する（[拡張プロファイル仕様](../01_EARS-AI規格/02_拡張プロファイル仕様.md) §3）。

`verify.commands`は仕様作成だけの段階では省略できる。`bitz verify`を実行するときに対象のコマンドが
定義されていなければ`blocked`とする。

Contextの上限は完全な依存閉包を部分的に切り捨てるためではない。上限を超えた場合は`blocked`とし、
利用者が依存の分割またはhard limit内での明示的な上限変更を判断する。

`workspace.id`は`[a-z][a-z0-9-]{0,31}`とする。`monorepo.members`は`maxMembers`以下かつhard limit
100件以下とし、各要素の`id`はmember側`workspace.id`と一致させる。`path`はGitルート相対とし、絶対パス、
`..`、glob、symlink、Git submodule、member同士の重複・入れ子を禁止する。member設定で`monorepo`を
宣言してはならない。`monorepo.maxMembers`だけを`members`なしで指定することも禁止する。詳細は
[モノレポSPEC連合仕様](12_モノレポSPEC連合仕様.md)を正とする。

## 4. 検証コマンド

`verify.commands`のキーは`[a-z][a-z0-9-]{0,31}`とする。値は空でない文字列配列、または`argv`と任意の
`cwd`を持つmapとする。配列形式は`argv`だけを持つ短縮記法である。Coreはシェルを介さずargvとして起動する。

```yaml
verify:
  commands:
    default: [pytest, -q, "{tests}"]
    frontend:
      argv: [npm, test, "--", "{tests}"]
      cwd: frontend
```

`{tests}`は配列要素全体として1回だけ使用でき、対象要求の`tests`を1パスずつ独立したargv要素へ展開する。
展開は1回の実行へまとめ、パスごとにプロセスを分けない。文字列の一部への埋込み、環境変数展開、
コマンド置換、パイプ、リダイレクトは行わない。`{tests}`がなければ、対応するテストパスの件数にかかわらず
設定されたargvをそのまま1回実行する。

検証コマンドbindingは`(workspaceId, 正規化した argv template, 正規化した cwd)`で識別する。commandsのキーは
可読ラベルであり、名前が異なっても正規化後のargv templateと`cwd`が一致する定義は同一bindingとして
1回だけ実行する。重複排除の単位と実行回数は
[ADR-030](../../02.設計書/10_決定記録/ADR-030_verify実行bindingの正規識別子と重複排除単位の統一.md)を正とする。

`cwd`はワークスペースルート相対の既存ディレクトリとし、絶対パス、`..`、シンボリックリンクによる
ルート外参照を禁止する。モノレポmemberではmember root外、連合ルートでは登録member配下を指定できない。
`cwd`指定時は全テストパスがその配下にあることを要求し、`{tests}`へは`cwd`相対へ
正規化したパスを展開する。実行ファイルはPATHから解決する。SPEC文書のFrontmatterや本文は、コマンド、
引数、環境変数、作業ディレクトリを定義できない。

## 5. 実効設定

コマンドライン引数は対象範囲、Git比較基準、出力形式、レポート生成、タイムアウト短縮だけを変更できる。
タイムアウト延長、保護解除、検証コマンド差替えは行わない。

`bitz check --base <git-revision>`は設定の保護を解除する値ではなく、変更範囲、状態遷移、
承認済みREQ保護、TASK境界が共通利用する比較元を明示する。未指定時は`HEAD`を使用し、解決済みcommit IDを
結果の`revision.base`へ記録する。

`bitz verify --timeout <seconds>`は1以上3600以下の整数capとする。各workspaceの実効値は
`min(CLI指定値, verify.timeoutSeconds)`であり、CLIから設定timeoutを延長できない。未指定時は設定値を使い、
実効値をcommand結果へ記録する。

`bitz check`、`bitz verify`、`bitz doctor`の`--format json`は、秘密情報を含まない実効設定を結果へ含めてよい。
Core 1.0は`.env`を読み込まず、設定値の文字列補間を行わない。

## 6. 解析制約

- UTF-8のYAML 1.2 subsetとして解析する。
- カスタムタグ、アンカー、エイリアス、merge keyを禁止する。
- 重複キーをエラーとする。
- ファイルサイズ上限を64 KiBとする。
- Parserはネットワークアクセスを行わない。
