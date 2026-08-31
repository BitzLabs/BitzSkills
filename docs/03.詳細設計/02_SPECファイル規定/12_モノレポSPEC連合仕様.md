# モノレポSPEC連合仕様 1.0

## 1. 目的と用語

本仕様は、1つのGitリポジトリに複数の`.spec/`を置き、個別プロジェクトの独立性と横断要求の
完全解決を両立する規則を定める。

| 用語 | 意味 |
|---|---|
| repository root | 対象Gitリポジトリのルート |
| workspace | 1つの`.spec/bitz.yaml`と、その親ディレクトリが所有するSPEC・コード・テスト |
| federation root | repository rootにある`.spec/bitz.yaml`。連合カタログと共通SPECを所有する |
| member | `monorepo.members`へ明示登録された子workspace |
| active workspace | 通常操作の設定、ローカルID、レポート出力先を決めるworkspace |

Git submodule、別Gitリポジトリ、ネットワーク上のSPECは連合へ含めない。

## 2. 標準配置

```text
repository/
├── .spec/
│   ├── bitz.yaml
│   ├── requirements/
│   └── decisions/
├── apps/web/
│   ├── .spec/
│   │   ├── bitz.yaml
│   │   ├── requirements/
│   │   └── technical/
│   └── src/
├── services/api/
│   ├── .spec/
│   │   └── bitz.yaml
│   └── src/
└── libs/native/
    ├── .spec/
    │   └── bitz.yaml
    └── src/
```

federation rootはrepository root直下に限る。member pathはrepository root相対の実ディレクトリとし、
絶対パス、`..`、glob、symlink、Git submoduleを禁止する。member同士は同一path、親子pathになってはならない。

## 3. 設定

federation rootの例:

```yaml
schemaVersion: "1.0"
language: ja
earsAi: "1.0"
workspace:
  id: platform
monorepo:
  maxMembers: 20
  members:
    - id: web
      path: apps/web
    - id: api
      path: services/api
    - id: native
      path: libs/native
```

memberの例:

```yaml
schemaVersion: "1.0"
language: ja
earsAi: "1.0"
workspace:
  id: web
```

- `workspace.id`は`[a-z][a-z0-9-]{0,31}`とし、連合内で一意にする。
- `monorepo.maxMembers`は既定20、hard limit 100とし、`members`は実効上限を超えてはならない。
- catalogの`id`とmember側`workspace.id`は一致しなければならない。
- memberは`monorepo`を宣言できない。連合の入れ子を禁止する。
- 設定継承、環境変数によるmember追加、暗黙の`.spec/`再帰探索を行わない。
- 単一workspaceでは`workspace.id`を省略でき、実効値を`root`とする。連合参加時は省略できない。

## 4. active workspaceと探索

1. 指定パスまたは現在ディレクトリから親方向へ探索し、最も近い`.spec/bitz.yaml`を候補にする。
2. Git rootにfederation rootがあり、候補が`monorepo.members`へ登録されていれば、そのmemberをactiveにする。
3. 候補がGit rootの設定ならfederation rootをactiveにする。
4. federation rootが存在する状態で、選択された別`.spec/`がcatalogへ未登録なら、単独workspaceとして
   暗黙利用せず`SPEC-MONOREPO-UNREGISTERED-001`で`blocked`にする。未登録`.spec/`を見つけるための
   リポジトリ全体探索は行わない。
5. `--workspace <id>`指定時はcatalogから完全一致で選択する。未知IDは`failed`にする。

通常の`check`と`verify`はactive workspaceを対象にする。`--all-workspaces`はfederation rootでだけ許可し、
rootを先頭、その後をworkspace ID辞書順で処理する。
`--workspace`と`--all-workspaces`は排他的とする。`check --all-workspaces`は`--full`を含意し、対象ID・pathを
受け付けない。`verify --all-workspaces`も引数なしverifyを各workspaceへ適用し、対象ID・pathを受け付けない。
明示`verify`のSPECファイルpathは選択workspace内のREQ、TECH、TASKだけを受け付け、Frontmatter IDへ
正規化する。コードpath、テストpath、ディレクトリ、ADRを受け付けない。

## 5. 修飾ID

| 対象 | ローカル表現 | 連合正規表現 |
|---|---|---|
| 文書 | `REQ-001` | `web::REQ-001` |
| 規範文 | `REQ-001:AC-01` | `web::REQ-001:AC-01` |

Frontmatterの`id`、ファイル名、EARS-AI行の規範文IDには従来どおりローカル表現を記述する。修飾IDは
関係のtarget、CLI起点、Core結果で使う連合上の識別子であり、文書自身の`id`へ書き込まない。

同じworkspace内のFrontmatter関係ではローカル表現を許可する。別workspaceを参照する場合は必ず連合正規表現を
使用する。Coreは非修飾IDを他workspaceから探索せず、同名IDの近さや探索順で解決しない。

Context Bundle、Diagnosticの`specRefs`、全体検査・検証結果では連合正規表現を使用する。単一workspaceの
既存出力は後方互換のためローカル表現を維持してよいが、JSONに`workspace.id`を含める。

1回の`context`に指定する起点はすべて同じworkspaceが所有しなければならない。その所有workspaceを
request workspaceとし、Context上限と非修飾IDの解決基準にする。別workspaceは強い依存として到達させ、
独立した複数workspaceの起点はrequestを分ける。

## 6. 所有パス

memberの`implements`、`tests[].path`、TASK `changes`、`verify.commands[].cwd`はmember root相対とし、
member外を参照できない。federation rootはrepository root相対だが、登録member配下を所有パスとして指定できない。

共通要求が複数memberへ実装を要求する場合、共通REQを各memberのREQまたはTECHが`refines`し、member側文書が
実装・テストパスを所有する。member側refinementの`tests[].covers`は、自身が直接`refines`する
別workspaceの規範文、または直接`refines`する文書が所有する規範文を修飾IDで指定できる。それ以外の
別文書・別workspaceの句を任意にcoverしてはならない。
横断TASKはmemberごとのTASKへ分割し、root TASKから修飾IDで`requires`できる。

例として、`platform::REQ-001:AC-01`をweb workspaceが具体化・検証するTECHは次のように記述する。

```yaml
---
id: TECH-010
title: Webログイン実装
status: approved
relations:
  refines:
    - platform::REQ-001:AC-01
implements:
  - src/auth/login.ts
tests:
  - path: tests/auth/login.test.ts
    covers:
      - platform::REQ-001:AC-01
    command: frontend
---
```

この対応は、`web::TECH-010`が直接refineする句だけに有効であり、同じ共通REQの別の句へ暗黙に広げない。

## 7. 横断関係とContext Resolution

Coreは連合全体の軽量Frontmatter索引を作り、修飾された強い関係を通常の型規則で解決する。`context`は
起点から到達可能な文書だけをBundleへ収録し、関係しないworkspaceの本文を含めない。

横断Contextでは次を追加する。

- `workspace.id`、repository root相対`workspace.path`
- 文書ごとの`workspaceId`と修飾ID
- workspace境界を越えるedge
- 起点workspaceのContext上限と、Core hard limit

Context Digestには、到達したworkspace IDとpath、修飾起点、修飾edge、各workspaceの解釈に影響する実効設定を
含める。絶対パスと未到達workspaceの設定は含めない。

## 8. 検査と検証

`bitz check --all-workspaces`は次を検査する。

1. catalogとmember設定
2. workspace IDとpathの一意性、非重複性
3. SchemaとEARS-AIのmajor互換性。Profileの互換性はCore 1.0では判定しない
4. 連合全体の修飾ID索引と横断関係
5. workspaceごとのSPEC、所有パス、検証コマンド
6. 横断逆参照による影響候補

`bitz verify --all-workspaces`はworkspaceごとにContextを解決し、テストを所有するworkspaceの設定で実行する。
横断refinementが共通規範文をcoverする場合も、テスト所有workspaceのコマンドと`cwd`を使用する。実行単位は
`(workspace-id, command, test-path)`で識別する。`cwd`はコマンド定義に従属するため識別子へ含めない。
コマンド名が同じでもworkspaceが異なれば統合しない。実行済み集合は連合全体で1つとし、
横断refinementが参照する同一テストを二重に実行しない。
結果はworkspace別に保持し、集約statusは通常の最悪値規則を使う。
失敗したworkspaceがあっても、独立した後続workspaceは可能な範囲で継続する。

全体操作のJSONは次の共通外形を持つ。

```json
{
  "schemaVersion": "1.0",
  "operation": "check",
  "scope": "all-workspaces",
  "status": "passed_with_warnings",
  "federation": {"id": "platform", "path": "."},
  "workspaces": [
    {"id": "platform", "path": ".", "status": "passed"},
    {"id": "api", "path": "services/api", "status": "passed_with_warnings"},
    {"id": "web", "path": "apps/web", "status": "passed"}
  ],
  "diagnostics": []
}
```

`workspaces`は実行順と同じ順序を保ち、各要素に対象別Diagnostic、検証時はcommandsとdurationを追加できる。

`--report`を指定した全体操作の集約レポートはfederation rootの`.spec/reports/`へ保存し、member別結果に
workspace IDを含める。member単独操作のレポートはmember自身の`.spec/reports/`へ保存する。

## 9. 上限と性能

- SPECファイル10,000件、関係・索引のリソース上限は連合全体へ適用する。
- Context文書数とbytesは起点workspaceの設定を使用し、既存のhard limitを超えられない。
- 通常操作でも横断参照と逆参照に必要な連合全体の軽量索引を作る。
- 変更workspaceと到達workspaceの完全解析を優先し、無関係workspaceの本文解析を避ける。
- `--all-workspaces`の性能目標はPhase 0で基準モノレポfixtureを固定してから確定する。
- Gitを利用できない場合、単一workspaceの縮退動作は維持するが、連合境界とmember所有を確定できないため
  モノレポ操作は`blocked`とする。

## 10. Diagnostic

| コード | severity | result status | 条件 |
|---|---|---|---|
| `SPEC-MONOREPO-CONFIG-001` | error | `failed` | `monorepo`設定の型、件数、配置が不正 |
| `SPEC-MONOREPO-MEMBER-001` | error | `failed` | memberの設定不在、またはcatalogとのID不一致 |
| `SPEC-MONOREPO-VERSION-001` | error | `blocked` | memberの`schemaVersion`または`earsAi`が未対応major |
| `SPEC-MONOREPO-PATH-001` | error | `failed` | member pathが不正、重複、入れ子、symlink、submodule |
| `SPEC-MONOREPO-ID-001` | error | `failed` | workspace IDが不正または重複 |
| `SPEC-MONOREPO-UNREGISTERED-001` | error | `blocked` | federation内で選択した`.spec/`がcatalogへ未登録 |
| `SPEC-MONOREPO-REF-001` | error | `failed` | 横断参照が非修飾、またはworkspaceを解決できない |
| `SPEC-MONOREPO-OWNERSHIP-001` | error | `failed` | SPEC、コード、テスト、TASK、cwdが所有境界を越える |
| `SPEC-MONOREPO-LIMIT-001` | error | `blocked` | member数または連合全体のリソース上限を超えた |
| `SPEC-MONOREPO-GIT-001` | error | `blocked` | Gitを利用できず連合境界と所有範囲を確定できない |

severityとresult statusは
[ADR-021](../../02.設計書/10_決定記録/ADR-021_Diagnostic-severity・操作status・source-Schemaの分離.md)に従う。

## 11. 非目標

- 複数Gitリポジトリまたはネットワーク越しのSPEC連合
- Git submodule内SPECの横断解決
- member設定の継承・上書き
- workspace間の検証コマンド統合
- Core 1.0での全体検査・検証の必須並列化
