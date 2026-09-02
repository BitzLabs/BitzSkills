# workspace・設定仕様

## 1. workspace決定

Core 1.0は単一workspaceと、1つのGit repository内の明示的なworkspace連合を扱う。

1. 指定pathまたはcurrent directoryから親方向へ`.spec/bitz.yaml`を探索する。
2. Git利用時はrepository境界を越えない。
3. 最初に見つかった設定の親directoryをworkspace rootとする。
4. 見つからなければ`blocked`とする。
5. symlinkを辿ってworkspace外のSPECを読み込まない。

単一workspaceの実効IDは`workspace.id`、省略時は`root`とし、pathは`.`とする。Git rootの設定が
`monorepo.members`を宣言する場合は、
[モノレポSPEC連合仕様](05_モノレポSPEC連合仕様.md)のcatalog検証、active workspace決定、所有境界を適用する。

## 2. 標準配置

```text
.spec/
├── bitz.yaml
├── requirements/
│   └── REQ-001-user-login.md
├── technical/
│   └── TECH-001-token-storage.md
├── decisions/
│   └── ADR-001-token-format.md
├── tasks/
│   └── TASK-001-login-endpoint.md
└── reports/
```

`.spec/bitz.yaml`だけを必須とし、各directoryは必要になった時点で作成する。要求が1件以上ある場合は
`requirements/`を使用する。`reports/`は既定でGit管理外とする。

## 3. 探索対象

| path | 種別 | check |
|---|---|---|
| `.spec/bitz.yaml` | 設定 | 常に |
| `.spec/requirements/**/*.md` | REQ | 対象選択に従う |
| `.spec/technical/**/*.md` | TECH | 対象選択に従う |
| `.spec/decisions/**/*.md` | ADR | 対象選択に従う |
| `.spec/tasks/**/*.md` | TASK | 存在時 |
| `.spec/reports/*.json` | 結果 | 入力にしない |

`.spec/`内の未知file/directoryはwarningとする。hidden、一時file、Markdown以外の成果物を暗黙にSPECとして
読み込まない。

## 4. `bitz.yaml`

```yaml
schemaVersion: "1.0"
language: ja
earsAi: "1.0"
context:
  maxDocuments: 20
  maxBytes: 131072
verify:
  timeoutSeconds: 300
  commands:
    default:
      argv: [pytest, -q, "{tests}"]
      cwd: .
safety:
  protectApprovedRequirements: true
```

## 5. Schema

| key | 型 | 必須 | 既定 | 制約 |
|---|---|:--:|---|---|
| `schemaVersion` | string | Yes | — | Core 1.0では`"1.0"` |
| `language` | string | No | `ja` | BCP 47 language tag |
| `earsAi` | string | Yes | — | `major.minor` |
| `context.maxDocuments` | integer | No | `20` | 1〜100 |
| `context.maxBytes` | integer | No | `131072` | 4,096〜1,048,576 |
| `verify.timeoutSeconds` | integer | No | `300` | 1〜3,600 |
| `verify.commands` | map | No | `{}` | command名からbinding定義 |
| `safety.protectApprovedRequirements` | boolean | No | `true` | Git差分保護 |
| `workspace.id` | string | No | `root` | `[a-z][a-z0-9-]{0,31}`。連合root/memberは必須 |
| `monorepo.members` | object[] | No | — | federation rootだけ。`id`とrepository root相対`path` |
| `monorepo.maxMembers` | integer | No | `20` | 1〜100。`members`指定時だけ使用可 |

`monorepo.members`要素は次のfieldだけを持つ。

| key | 型 | 必須 | 制約 |
|---|---|:--:|---|
| `id` | string | Yes | `workspace.id`と同じ字句規則。連合内で一意 |
| `path` | string | Yes | repository root相対directory。所有境界は連合仕様に従う |

`profiles`はCore 1.0の標準keyではない。検出した場合は将来scopeの設定としてwarningし、判定、Context Digest、
操作へ使用しない。`workspace`と`monorepo`の組合せ、member field、path制約は
[モノレポSPEC連合仕様](05_モノレポSPEC連合仕様.md)が定義する。

未知の標準keyは同一majorの前方互換性のためwarningし、値を変更しない。型不正と必須key欠如は`error`、
未知Schema majorは`blocked`とする。

`workspace`と`monorepo`は未リリースの初回Core 1.0 Schemaに含まれる。モノレポ非対応の公開済みCore 1.0との
移行分岐、追加feature marker、Schema major引上げは設けない。連合内のworkspace IDは永続identityであり、
初回連合化とbase/current対応は[モノレポSPEC連合仕様](05_モノレポSPEC連合仕様.md#41-workspace-identity)に従う。

## 6. command定義

command名は`[a-z][a-z0-9-]{0,31}`とする。値は空でないargv配列、または`argv`と任意`cwd`のmapとする。

```yaml
verify:
  commands:
    default: [pytest, -q, "{tests}"]
    frontend:
      argv: [npm, test, "--", "{tests}"]
      cwd: frontend
```

- shellを介さずargvとして起動する。
- `{tests}`は配列要素全体として0回または1回使用できる。
- `{tests}`は対象test pathを個別argv要素へ展開する。
- 文字列内埋込み、環境変数展開、command置換、pipe、redirectを行わない。
- `{tests}`がなければargvをそのまま1回実行する。
- `cwd`はworkspace相対の既存directoryとし、絶対path、`..`、root外symlinkを禁止する。
- `cwd`指定時、test pathはその配下に限り、argvへ`cwd`相対で展開する。
- command名をbinding IDとする。異なる名前の定義を内容が同じという理由で統合しない。

Frontmatterと本文はcommand argv、cwd、環境変数を定義できない。

## 7. 実効設定

CLIは対象範囲、Git比較基準、出力形式、report、timeout短縮だけを変更できる。保護解除、command差替え、
設定timeout延長を行わない。

`verify --timeout N`の実効値は`min(N, verify.timeoutSeconds)`とする。Coreは`.env`を読み込まず、設定値の
文字列補間を行わない。

## 8. YAML制約

- UTF-8のYAML 1.2 subset
- scalar、配列、通常mapだけ。object配列は`monorepo.members`だけで使用する
- custom tag、anchor、alias、merge keyを禁止
- 重複keyをerror
- file size 64 KiB以下
- network accessなし

## 9. path

SPECへ記録するpathはworkspace root相対、separatorは`/`とする。絶対path、`..`、NUL、glob、root外symlinkを
禁止する。Git管理外の生成物と依存cacheを`implements`または`tests`へ指定しない。
連合では、workspace root内であっても別memberの所有領域を参照できない。federation rootによるmember配下の
所有も禁止し、詳細は[モノレポSPEC連合仕様](05_モノレポSPEC連合仕様.md)に従う。
