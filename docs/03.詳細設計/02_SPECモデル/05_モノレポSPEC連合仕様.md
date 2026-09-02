# モノレポSPEC連合仕様 1.0

## 1. 所有範囲

本書は、1つのGit repositoryに複数の`.spec/`を置く連合のcatalog、識別子、所有境界、横断解決、全体操作を
定義する。単一workspaceの設定fieldは[workspace・設定仕様](01_workspace・設定仕様.md)、関係型と閉包は
[関係・トレースモデル](04_関係・トレースモデル.md)、操作固有の入力と結果は各[操作仕様](../03_操作仕様/README.md)
が所有する。本書はそれらを連合へ適用する差分だけを所有する。

| 用語 | 意味 |
|---|---|
| repository root | 対象Git repositoryのroot |
| workspace | 1つの`.spec/bitz.yaml`、SPEC、所有code/testからなる単位 |
| federation root | repository rootにあるworkspace。連合catalogと共通SPECを所有する |
| member | `monorepo.members`へ明示登録された子workspace |
| active workspace | workspace単独操作のローカルID、設定、report出力先を決めるworkspace |
| request workspace | `context`の全起点を所有し、上限と非修飾IDの解決基準になるworkspace |

## 2. 配置とcatalog

```text
repository/
├── .spec/                       # federation root・共通要求
│   └── bitz.yaml
├── apps/web/
│   └── .spec/bitz.yaml          # web member
├── services/api/
│   └── .spec/bitz.yaml          # api member
└── libs/native/
    └── .spec/bitz.yaml          # native member
```

federation rootはrepository root直下だけに置く。root設定例を次に示す。

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

memberは自身の設定を持つ。

```yaml
schemaVersion: "1.0"
language: ja
earsAi: "1.0"
workspace:
  id: web
```

- federation rootと全memberで`workspace.id`を必須とし、連合内で一意にする。
- catalogの`id`とmember設定の`workspace.id`は一致させる。
- memberは`monorepo`を宣言できず、連合を入れ子にしない。
- member pathはrepository root相対の実directoryとする。絶対path、`.`、空path、`..`、glob、symlink、
  Git submodule、別Git repositoryを禁止する。
- member path同士の同一、親子、実path解決後の重複を禁止する。
- 設定、command、安全設定、Context上限を継承しない。各workspaceは自身の`bitz.yaml`だけを使用する。
- `language`はworkspaceごとに異なってよく、言語差だけで連合を不適合にしない。SchemaとEARS-AIの未知majorは
  安全に横断解決できないため`blocked`とする。
- catalogにない`.spec/`を暗黙に追加しない。workspace単独操作ではrepository全体を探索せず、選択経路上の
  未登録設定だけを拒否する。全体操作は§8のGit既知設定preflightを行うが、filesystem全体の任意directoryは
  再帰探索しない。

`monorepo.maxMembers`の既定は20、指定範囲は1〜100、Core hard limitは100とする。`members`が実効上限を
超えれば`blocked`とする。0 memberの`monorepo`は設定不適合とする。

## 3. workspace決定

Coreは先にGit repository rootを確定し、次の順でworkspaceを決める。

1. repository rootの`.spec/bitz.yaml`に`monorepo.members`がなければ、通常の単一workspace探索を使う。
2. 連合では、指定pathまたはcurrent directoryからrepository rootへ親方向に探索し、最も近い
   `.spec/bitz.yaml`を候補にする。
3. 候補がrepository root設定ならfederation root、catalogのpathと設定IDが一致すれば該当memberをactiveにする。
4. 連合内で選択された別`.spec/`がcatalogにない場合は、単独workspaceとして使わず
   `SPEC-MONOREPO-UNREGISTERED-001`／`blocked`とする。
5. `--workspace <id>`はcatalog内のrootまたはmember IDと完全一致でactive workspaceを置き換える。字句不正、
   構文上妥当だがcatalogにないIDはともにinvocation errorとして終了コード4とし、操作結果とreportを生成しない。

`--workspace`を使わないpath入力はactive workspace内に限る。修飾IDを起点にする場合は、その所有workspaceを
選択する。複数起点が異なるworkspaceを所有する場合、または`--workspace`と起点所有者が一致しない場合は
引数不正とする。

## 4. 識別子と解決

| 対象 | workspace内表現 | 連合正規表現 |
|---|---|---|
| 文書 | `REQ-001` | `web::REQ-001` |
| 規範文 | `REQ-001:AC-01` | `web::REQ-001:AC-01` |

```ebnf
qualified-document-id  = workspace-id, "::", document-id ;
qualified-statement-id = workspace-id, "::", statement-id ;
```

`workspace-id`は`[a-z][a-z0-9-]{0,31}`、`document-id`と`statement-id`はEARS-AIの字句規則を使う。
`::`は連合の解決envelopeであり、文書自身のID階層やEARS-AI規範文IDの2階層規則を変更しない。

Frontmatterの`id`、file名、EARS-AI行のIDはworkspace内表現を使う。`relations`と`tests[].covers`は同じworkspaceを
参照するとき非修飾形式を許可し、別workspaceを参照するとき連合正規形式を必須とする。Coreは非修飾IDを
別workspaceから探索しない。

連合内で実行したCore操作の`roots`、`targets`、`statements`、文書`id`、relation edge、Diagnostic `specRefs`は、
member単独操作を含め連合正規形式で返す。`source.path`と文書`path`は各workspace root相対とし、
`source.workspaceId`または文書`workspaceId`との組で一意にする。単一workspaceの非修飾出力は維持する。

文書IDと規範文IDはworkspace内で一意とする。同じローカルIDを別workspaceが持つことは許可する。

### 4.1 workspace identity

workspace IDは連合内の永続identityとし、Core 1.0はrenameを推定または支援しない。base/current catalogで同じIDを
維持したmember path変更は同一workspaceの移動とする。ID変更は、pathが同じでも旧workspaceの削除と新workspaceの
追加として扱う。catalogからmemberを削除した場合、base側workspaceの管理済みSPECへ既存の削除検査を適用する。

単一workspaceから初めて連合化するGit比較に限り、baseがrepository rootの同じ`.spec`を使い、`monorepo`がなく、
`workspace.id`を省略している場合、baseの実効ID `root`をcurrentの明示federation root IDへ一方向写像する。
baseに明示IDがある場合はcurrentのfederation rootも同じIDを維持しなければならない。この写像はGit比較だけに使い、
連合化後の修飾IDとContext Digestを旧値のまま維持しない。

## 5. 所有境界

memberのSPEC、`implements`、`tests[].path`、TASK `changes`、`verify.commands[].cwd`はmember root配下だけを
所有する。federation rootのSPECはrepository rootに置くが、登録member配下を`implements`、test path、
TASK `changes`、command `cwd`として所有できない。memberの`.spec/`自体も別workspaceから所有できない。

共通要求を実装する場合、member側REQまたはTECHがroot／別memberのREQ、TECHまたは規範文を`refines`し、
実装pathとtest pathをmember側文書へ置く。`tests[].covers`が別workspaceの規範文を指定できるのは、そのtestを
宣言する文書が当該規範文、またはその所有文書を直接`refines`している場合だけとする。推移的なrefinementを
根拠に任意の横断coverageを宣言できない。

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

横断TASKはmemberごとのTASKへ分割し、federation root TASKから修飾`requires`で順序付ける。1つのTASKに複数の
workspaceの`changes`を持たせない。

### 5.1 canonical path判定

member path、SPEC path、`implements`、`tests[].path`、TASK `changes`、command `cwd`は、次の共通手順で
canonicalな所有領域を判定する。

1. Gitからrepository rootを確定し、その実pathを基準にする。
2. 入力をUTF-8／Unicode NFCと`/` separatorへ正規化する。
3. workspace rootまたはcommand `cwd`の`.`と、TASK directory prefixの末尾`/`を先に種別化する。それ以外の
   絶対path、空segment、`.`、`..`、NUL、globを拒否する。
4. 存在する各ancestorを`lstat`し、symlink解決後の実pathを得る。存在しない予定pathは、最も近い既存ancestorの
   実pathへ検査済みsuffixを連結する。
5. filesystemのcase sensitivityに従う比較keyを作り、path segment境界で包含を判定する。
6. Git metadataでもrepository root、worktree、submodule、別repositoryの境界を照合する。

member rootとworkspaceの`.spec/bitz.yaml`へ至るdirectoryはsymlinkを禁止する。code、test、TASK、cwdのsymlinkは
同じ所有領域内へ解決する場合だけ許可する。repository外、別workspace、memberの`.spec`へ解決すれば
`SPEC-MONOREPO-OWNERSHIP-001`とする。member実path同士の同一、親子、case-insensitive filesystemでの同一と、
nested repository／worktree、submoduleは`SPEC-MONOREPO-PATH-001`とする。

## 6. 横断索引とContext

Coreはcatalogに登録された全workspaceの軽量Frontmatter索引を作り、修飾された関係を通常の型規則で解決する。
`context`は全起点を同じrequest workspaceに限定し、強い関係で到達した文書だけを完全閉包へ含める。
関係しないworkspaceの本文は読み込まず、Bundleへ含めない。

Context Bundleは共通fieldに加えて次を持つ。

- top-level `workspace`はrequest workspace
- 各`documents[]`の`workspaceId`と連合正規`id`
- `resolution.workspaces[]`に到達workspaceの`id`とrepository root相対`path`
- `resolution.crossWorkspaceEdges[]`に`relation`、修飾`source`、修飾`target`

`resolution.workspaces`はrequest workspaceを先頭、その後をworkspace ID辞書順とする。
`resolution.crossWorkspaceEdges`は`source`、`relation`、`target`の辞書順とし、workspace境界を越えないedgeを
重複して収録しない。

連合Contextでは`documents[].workspaceId`、`resolution.workspaces`、`resolution.crossWorkspaceEdges`を必須とする。
`resolution.workspaces`は1件以上で、各要素は必須のstring `id`と`path`だけを持つ。
`resolution.crossWorkspaceEdges`は0件でも空配列を返し、各要素は次を持つ。

| field | 型 | 必須 | 制約 |
|---|---|:--:|---|
| `relation` | enum | Yes | `requires`、`refines`、`addresses`、`supersedes`、`related` |
| `source` | string | Yes | 修飾document ID |
| `target` | string | Yes | 修飾document IDまたはstatement ID |

単一workspaceではこれらの連合固有fieldと`documents[].workspaceId`を省略する。連合の各文書IDとedge IDは修飾形式、
文書pathは所有workspace相対とする。

Context Digestには、通常の材料に加えてrequest workspace ID、到達workspaceのIDとpath、修飾起点、修飾edgeを
含める。実効設定は到達workspaceで実際に使用した次のallowlistへ射影する。

- 到達workspaceごとの`schemaVersion`、`earsAi`、`language`
- request workspaceだけの既定値適用後`context.maxDocuments`と`context.maxBytes`
- 1件以上のbindingを収録したworkspaceの既定値適用後`verify.timeoutSeconds`
- Bundleが参照するcommandだけのcommand名、argv、既定値適用後cwd。command名辞書順

絶対path、未到達workspace、未使用command、`monorepo.members`の列挙順、`monorepo.maxMembers`、`safety`、出力形式、
report、CLI timeout capは含めない。設定不適合はDigest計算前に停止する。Context文書数とbyte上限はrequest workspaceの
設定を使い、Core hard limitを超えられない。

## 7. workspace単独操作の共通規則

`context`、`check`、`verify`、`doctor`の通常実行はactive workspaceを1つ選ぶ。横断関係の解決に必要な軽量索引と
到達先解析は行うが、無関係memberを完全検査しない。明示pathは選択workspace root相対で解決する。
別workspaceのpathをCLIへ直接渡さず、`--workspace`とそのworkspace相対path、または修飾IDを使う。

各操作が受け付ける対象、`--workspace`との排他、処理と結果は各[操作仕様](../03_操作仕様/README.md)が定義する。

## 8. 全体操作の共通規則

`check`、`verify`、`doctor`は、current directoryまたはadapterが渡した探索pathから同じGit repository rootと
federation rootを一意に発見できる場合に`--all-workspaces`を受け付ける。current directoryがrepository rootと
一致する必要はなく、member配下からも同じ連合全体を選択する。発見不能または曖昧な場合はinvocation error、
終了コード4とする。`--workspace`と排他的とする。

discoveryはGit rootとrepository root直下の`.spec/bitz.yaml`という候補pathを確定する段階であり、設定内容の適合を
要求しない。候補を一意に発見した後の構文、型、ID、catalog不適合はinvocation errorへ変えず、global preflightの
操作結果として返す。

全体操作はworkspace処理前に、Gitが認識する`.spec/bitz.yaml`候補とroot＋catalog設定をsnapshotごとに比較する。
現在snapshotではworking treeに存在するtracked／staged pathと未追跡かつ非ignore pathを対象にし、checkは指定base
snapshot、doctorはHEAD snapshotも対象にする。verifyは現在snapshotだけを対象にする。各snapshot自身のroot設定が
`monorepo`を宣言する場合だけ、そのsnapshot自身のcatalogとの差分を検査する。初回連合化前の単一workspace snapshotへ
repository全体の不存在保証を遡及適用しない。ignored path、submodule内部、別repositoryは列挙しない。集合差があれば
`SPEC-MONOREPO-UNREGISTERED-001`／`blocked`とし、暗黙memberにはしない。

catalog、workspace ID/path、Git境界、未対応Schema/EARS-AI major、連合resource上限をglobal preflightとする。
非成功ならmember処理とverify commandを開始せず、`workspaces: []`で結果を返す。

処理順はfederation rootを先頭、その後をworkspace IDのUnicode code point辞書順とする。Core 1.0は逐次実行し、
並列実行を公開契約にしない。あるworkspaceが非成功でも、依存しない後続workspaceは可能な範囲で継続する。
操作固有の対象選択、Git基準版、binding、0件判定は各[操作仕様](../03_操作仕様/README.md)が定義する。

## 9. 連合結果とreport

全体操作は共通結果の`workspace`の代わりに`federation`と`workspaces`を持つ。workspace処理順、Diagnostic配置、
集約status、件数、report出力先は[結果・Diagnostic・終了コード](../00_共通契約/01_結果・Diagnostic・終了コード.md)
が定義する。verifyの各member結果は操作仕様の`targetResults[]`を持ち、共有command実体は所有memberへ1回だけ置く。
`--report`なしの全体操作はstatusにかかわらずfileを作らない。

global preflightでroot設定の構文、型またはIDが不正で有効なidentityを構成できない場合だけ、`federation`を
`{"id": null, "path": "."}`とする。それ以外は有効なIDを必須とし、不正なraw値をidentityに使わない。

## 10. 上限とGit前提

- 次のCore resource上限を1つの連合snapshot全体へ適用する。

| dimension | hard limit | 数え方 |
|---|---:|---|
| `memberCount` | 100 | catalogのmember数。federation rootを除く |
| `specFileCount` | 10,000 | 全workspaceのSPEC Markdown数 |
| `inputBytes` | 256 MiB | 全設定とSPEC Markdownのraw byte合計 |
| `statementCount` | 100,000 | 全EARS-AI規範文数 |
| `relationEdgeCount` | 1,000,000 | 全`relations` edge数 |
| `traceEntryCount` | 1,000,000 | `implements`、test、`covers`、TASK `changes`の全項目数 |
| `commandDefinitionCount` | 10,000 | 全workspaceのcommand定義数 |
| `verifyBindingCount` | 10,000 | 1回のverify実行計画にあるbinding数 |

- `check --base`のbase/currentは各snapshotへ個別に同じ上限を適用する。重複参照は重複排除前に数える。
- 上限超過は連合全体を`SPEC-MONOREPO-LIMIT-001`／`blocked`とし、部分結果やcommand実行へ進まない。
- limit Diagnostic `evidence`は`dimension`、`limit`、早期停止時の`observedAtLeast`を持つ。正確な全件数を得るために
  超過後も入力を読み続けることは要求しない。
- 通常操作でも横断参照と逆参照に必要な軽量索引はcatalog全体から作る。
- 変更workspaceと到達workspaceを完全解析し、無関係workspaceの本文解析を避ける。
- Gitが利用できない、repository rootを確定できない、またはmember pathが別worktree／repositoryへ解決される場合、
  連合操作は`SPEC-MONOREPO-GIT-001`／`blocked`とする。単一workspaceの縮退契約は変更しない。

## 11. Diagnostic

| code | severity | `resultStatus` | 条件 |
|---|---|---|---|
| `SPEC-MONOREPO-CONFIG-001` | error | `failed` | `monorepo`の型、件数、配置、root条件が不正 |
| `SPEC-MONOREPO-MEMBER-001` | error | `failed` | member設定不在、catalogとのID不一致、nested federation |
| `SPEC-MONOREPO-VERSION-001` | error | `blocked` | memberのSchemaまたはEARS-AIが未対応major |
| `SPEC-MONOREPO-PATH-001` | error | `failed` | member pathが不正、重複、入れ子、symlink、submodule、別repository |
| `SPEC-MONOREPO-ID-001` | error | `failed` | workspace IDが不正または重複 |
| `SPEC-MONOREPO-UNREGISTERED-001` | error | `blocked` | 選択した設定、または全体preflightのGit既知設定がcatalogに未登録 |
| `SPEC-MONOREPO-REF-001` | error | `failed` | 横断参照が非修飾、またはworkspace／targetを解決不能 |
| `SPEC-MONOREPO-OWNERSHIP-001` | error | `failed` | SPEC、code、test、TASK、cwdが所有境界を越える |
| `SPEC-MONOREPO-LIMIT-001` | error | `blocked` | member数または連合全体resource上限を超過 |
| `SPEC-MONOREPO-GIT-001` | error | `blocked` | Git repository境界またはmember所有範囲を確定不能 |

## 12. 非目標

- 複数Git repository、network上のSPEC、Git submodule内SPECの連合
- workspace設定の継承、上書き、環境変数によるmember追加
- ID衝突の勝敗判定と自動改番
- workspace間commandの内容同一性による統合
- 全体操作の必須並列化とfail-fast option
