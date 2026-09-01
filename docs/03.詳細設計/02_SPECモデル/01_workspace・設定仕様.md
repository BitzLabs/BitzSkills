# workspace・設定仕様

## 1. workspace決定

Core 1.0は1つのGit repository内に1つのworkspaceを扱う。

1. 指定pathまたはcurrent directoryから親方向へ`.spec/bitz.yaml`を探索する。
2. Git利用時はrepository境界を越えない。
3. 最初に見つかった設定の親directoryをworkspace rootとする。
4. 見つからなければ`blocked`とする。
5. symlinkを辿ってworkspace外のSPECを読み込まない。

結果上のworkspaceは常に`{"id":"root","path":"."}`とする。`workspace.id`、`monorepo`、member探索、
修飾ID、`--all-workspaces`はCore 1.0で受け付けない。

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

`profiles`、`workspace`、`monorepo`はCore 1.0の標準keyではない。検出した場合は将来scopeの設定としてwarningし、
判定、Context Digest、操作へ使用しない。

未知の標準keyは同一majorの前方互換性のためwarningし、値を変更しない。型不正と必須key欠如は`error`、
未知Schema majorは`blocked`とする。

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
- scalar、scalar配列、通常mapだけ
- custom tag、anchor、alias、merge keyを禁止
- 重複keyをerror
- file size 64 KiB以下
- network accessなし

## 9. path

SPECへ記録するpathはworkspace root相対、separatorは`/`とする。絶対path、`..`、NUL、glob、root外symlinkを
禁止する。Git管理外の生成物と依存cacheを`implements`または`tests`へ指定しない。
