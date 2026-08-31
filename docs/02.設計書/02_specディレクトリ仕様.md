# `.spec/` ディレクトリ設計

## 1. 目的

`.spec/`は、個人から数人のチームがAIと共有する小さな仕様契約である。チャット履歴は正本にせず、
確定した要求、設計判断、コード・テストとの対応だけを保持する。

## 2. Core 1.0の標準構造

```text
.spec/
├── bitz.yaml                  # 単一設定ファイル
├── requirements/             # EARS-AI要求（REQ）
├── technical/                # 必要な場合だけ置く技術仕様（TECH）
├── decisions/                # ADR
├── tasks/                    # 進行中タスク。任意
└── reports/                  # 失敗時または--report指定時だけ生成
```

`domain/`、`research/`、`quality/profiles/`、永続run状態、生成物ディレクトリはCore 1.0の必須構造にしない。
利用者が通常の`docs/`やIssueを使っている場合、それらを重複して`.spec/`へコピーしない。

### 2.1 モノレポ

Core 1.0は、1つのGitリポジトリに複数の`.spec/`を置くモノレポ連合を扱う。

```text
repository/
├── .spec/                  # 連合カタログと共通要求
├── apps/web/.spec/         # web固有SPEC
├── services/api/.spec/     # api固有SPEC
└── libs/native/.spec/      # native固有SPEC
```

Gitルートの`.spec/bitz.yaml`へmemberのIDとpathを明示し、各memberも自己完結した設定を持つ。
文書IDはworkspace内で一意とし、横断参照では`web::REQ-001`のような修飾IDを使用する。通常操作は
最寄りworkspaceだけを対象とし、横断Contextは型付き依存で到達するSPECだけを含める。
配置、所有境界、全体操作は[モノレポSPEC連合仕様](../03.詳細設計/02_SPECファイル規定/12_モノレポSPEC連合仕様.md)、
採用理由は[ADR-017](10_決定記録/ADR-017_モノレポSPEC連合をCore-1.0へ含める.md)を正とする。

## 3. 設定

設定は`.spec/bitz.yaml`だけを正本とする。

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
    default: [pytest, -q, "{tests}"]
safety:
  protectApprovedRequirements: true
```

モノレポ連合ルートは`workspace.id`と`monorepo.members`を追加し、member設定を継承しない。

個人・小規模チームではリポジトリ管理者を信頼し、設定変更はGit diffとレビューで管理する。
`policy`と`local`の二層スコープ、外部署名、専用override権限は導入しない。

環境変数やコマンド引数は、出力形式、タイムアウト、一時領域、`--full`、Git比較基準など
実行上の便宜だけを変更できる。
設定値を変更した実行は、実効値を`--format json`の結果へ含める。

## 4. 共通Frontmatter

```yaml
---
id: REQ-001
title: 認証
status: approved
relations:
  requires:
    - ADR-001
implements:
  - src/auth/service.ts
tests:
  - path: tests/auth/service.test.ts
    covers:
      - REQ-001:AC-01
    command: default
verify: default
---
```

必須項目は`id`、`title`、`status`とする。`implements`と`tests`は検証対象になった時点で追加する。
依存は`relations`の型付き語彙で表し、汎用`refs`を使用しない。owner、日時などは必要なプロジェクトだけが拡張する。

ファイル形式、項目の型、検証コマンドの安全な展開は
[SPECファイル規定](../03.詳細設計/02_SPECファイル規定/README.md)を正とする。

## 5. EARS-AI規範文

```markdown
- [REQ-001:AC-01] [ACTOR:AuthService] [WHEN] 有効な認証情報を受信した場合 [MUST] [THEN] アクセストークンを1件発行する。
```

規範文IDは`<文書ID>:<ローカルID>`の2階層とし、1規範文を1行で記述する。
Core構文の正は[EARS-AI Core構文仕様](../03.詳細設計/01_EARS-AI規格/01_Core構文仕様.md)とする。

## 6. トレース

Core 1.0は次の最小トレースだけを扱う。

```text
起点REQ/AC -> 型付き依存の完全閉包 -> 実装ファイル
                                  -> 句単位テスト対応 -> 現在の検証実行
```

- 依存閉包は`bitz context`でエージェントへ渡す。
- 関係の型、参照先、循環は`bitz check`で検査する。
- テストの実行結果は`bitz verify`で確認する。
- リンクが存在するだけで、要求を満たしたとは判定しない。
- 任意ワークフローDAG、コードシンボル単位の対応、意味的依存推定は対象外とする。
- モノレポでは修飾IDの横断関係を同じ閉包規則で解決し、関係しないworkspaceはContextへ含めない。

## 7. 状態

要求文書と技術仕様の状態は次の3つに限定する。

| 状態 | 意味 |
|---|---|
| `draft` | 編集中 |
| `approved` | 人間が意味を確認済み |
| `outdated` | 上位要求または実装変更の影響候補 |

許可遷移は`draft -> approved`、`approved -> draft|outdated`、
`outdated -> draft|approved`と同一状態の維持とする。作成時は`draft`または`approved`を選択できる。
ADRとTASKを含む状態遷移の正は
[Frontmatter共通仕様](../03.詳細設計/02_SPECファイル規定/03_Frontmatter共通仕様.md) §5と
[ADR-024](10_決定記録/ADR-024_SPEC文書の状態遷移契約.md)とする。

`verified`は文書状態ではなく、特定時点の`bitz verify`実行結果として扱う。`review`、`implementing`、
run状態機械はCore 1.0の共通契約に含めない。進行中状態はGit、Issue、または利用中のAI CLIが管理する。

## 8. 文書スタイル

REQ、TECH、ADR、TASKは、種別ごとにH1とH2の構成を固定する。太字ラベルを見出しの代わりにせず、
自由な詳細化はH3以下へ置く。正規構成は
[Markdown本文構成・スタイル](../03.詳細設計/02_SPECファイル規定/08_Markdown本文構成・スタイル.md)を正とする。

## 9. レポート

- 成功時は既定でファイルを生成しない。
- `failed`、`blocked`、`error`では再現に必要な対象、Diagnostic、コマンド、終了コードを自動保存する。
- `--report`指定時は`.spec/reports/<timestamp>-<operation>.json`へ保存する。
- 引数不正の終了コード4ではworkspace結果を生成していないため保存しない。
- `.spec/reports/`は既定で`.gitignore`対象とし、長期証跡はCI artifactまたはPR添付へ保存する。
- ULID、追記型台帳、永続ロックはCore 1.0で必須にしない。
- 同時書込みはGit worktreeまたはOSの単純な一時ファイル置換で衝突を避ける。

## 10. 安全な更新

- UTF-8を使用する。
- 自動更新は一時ファイルへ書き、検証後に置換する。
- 承認済みREQの本文は自動更新しない。
- コードから仕様への同期は提案diffだけを生成し、人間が採否を決める。
- キャッシュは`.gitignore`対象とし、いつでも再生成可能にする。

## 11. 言語

Core 1.0では1workspaceのSPEC記述言語を揃えることを推奨するが、連合内でworkspaceごとに異なる言語を
使用でき、異なる言語の文書を即時エラーにはしない。
同一規範文の自動翻訳同期は対象外とする。
