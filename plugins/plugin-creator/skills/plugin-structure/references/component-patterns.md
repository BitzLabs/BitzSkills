# コンポーネント整理パターン

プラグインのコンポーネントを効果的に整理するための発展パターン集。

## コンポーネントのライフサイクル

### 発見フェーズ（Discovery）

Claude Code 起動時:

1. 有効なプラグインの `.claude-plugin/plugin.json` を読む
2. デフォルトパスとカスタムパスからコンポーネントを発見する
3. YAML frontmatter と各種設定をパースする
4. コンポーネントを登録する
5. MCPサーバーの起動・フックの登録を行う

登録は初期化時に一度だけ行われる（常時監視ではない）。

### 活性化フェーズ（Activation）

- **コマンド**: ユーザーがスラッシュコマンドを入力 → 検索 → 実行
- **エージェント**: タスク発生 → 能力を評価 → エージェント選択
- **スキル**: タスクの文脈が description と一致 → スキル読み込み
- **フック**: イベント発生 → 一致するフックを呼び出し
- **MCPサーバー**: ツール呼び出しがサーバーの能力と一致 → 転送

## コマンドの整理パターン

### フラット構成

```
commands/
├── build.md
├── test.md
├── deploy.md
└── review.md
```

**適する場面**: コマンドが5〜15個で、抽象度が同じレベルのとき。
設定不要で発見も速い。

### カテゴリ別構成

```
commands/              # コアコマンド
admin-commands/        # 管理用
workflow-commands/     # ワークフロー自動化
```

マニフェストでカスタムパスを追加する:

```json
{
  "commands": ["./commands", "./admin-commands", "./workflow-commands"]
}
```

**適する場面**: コマンドが15個以上あり、機能カテゴリが明確なとき。

### 階層構成

```
commands/
├── ci/          (build.md, test.md, lint.md)
├── deployment/  (staging.md, production.md)
└── management/  (config.md, status.md)
```

**注意**: ネストしたフォルダは自動発見されないので、カスタムパスで
各サブフォルダを列挙する:

```json
{
  "commands": ["./commands/ci", "./commands/deployment", "./commands/management"]
}
```

**適する場面**: コマンドが20個以上で多段のカテゴリ分けが必要なとき。

## エージェントの整理パターン

| パターン | 例 | 適する場面 |
| --- | --- | --- |
| 役割別 | `code-reviewer.md`, `test-generator.md`, `refactorer.md` | 役割が明確に分かれ、手動起動が中心 |
| 能力別 | `python-expert.md`, `api-specialist.md`, `database-specialist.md` | 技術・ドメイン特化、自動選択させたい |
| 工程別 | `planning-agent.md`, `implementation-agent.md`, `testing-agent.md` | 順次ワークフロー・パイプライン自動化 |

## スキルの整理パターン

### トピック別

```
skills/
├── api-design/SKILL.md
├── error-handling/SKILL.md
└── testing-strategies/SKILL.md
```

知識・リファレンス提供が主目的のスキルに向く。

### ツール別

```
skills/
├── docker/
│   ├── SKILL.md
│   └── references/dockerfile-best-practices.md
└── kubernetes/
    ├── SKILL.md
    └── examples/deployment.yaml
```

特定ツールの専門知識・複雑な設定を扱うスキルに向く。

### ワークフロー別

```
skills/
└── deployment-workflow/
    ├── SKILL.md
    └── scripts/
        ├── pre-deploy.sh
        └── post-deploy.sh
```

複数ステップの手順・組織固有プロセスの自動化に向く。

### リソースをフル装備したスキル

```
skills/
└── api-testing/
    ├── SKILL.md              # 本体（目安1500語以内）
    ├── references/           # 詳細ガイド（必要時のみ読まれる）
    ├── examples/             # コピペ可能なコード例
    ├── scripts/              # 実行可能なスクリプト
    └── assets/               # テンプレート・設定ファイル
```

SKILL.md には概要と「いつどのリソースを使うか」だけを書き、
詳細は各フォルダへ分離する（progressive disclosure）。

## フックの整理パターン

### 一枚岩構成

```
hooks/
├── hooks.json     # 全フック定義
└── scripts/
    ├── validate-write.sh
    └── load-context.sh
```

フックが5〜10個で単純なうちはこれで十分。

### 目的別構成

```
hooks/
├── hooks.json
└── scripts/
    ├── security/   (validate-paths.sh, check-credentials.sh)
    ├── quality/    (lint-code.sh, check-tests.sh)
    └── workflow/   (notify-team.sh, update-status.sh)
```

スクリプトが多く、機能の境界が明確なとき。

**注意**: `hooks.json` の分割ファイル参照（`${file:...}` のような記法）は
サポートされていない。分割したい場合はビルドスクリプトで結合する。

## スクリプトの整理パターン

- **フラット**（`scripts/` 直下に5〜10個）: 単純なプラグイン向け
- **目的別**（`scripts/build/`, `scripts/test/`, `scripts/utils/`）: 10個以上で
  カテゴリが明確なとき
- **言語別**（`scripts/bash/`, `scripts/python/`）: 複数言語・ランタイム要件が
  異なるとき

## コンポーネント横断パターン

### 共有リソース

複数コンポーネントから共通ライブラリを参照する:

```
plugin/
├── commands/test.md       # lib/test-utils.sh を使う
├── hooks/scripts/pre-test.sh  # lib/test-utils.sh を source する
└── lib/
    └── test-utils.sh
```

```bash
#!/bin/bash
source "${CLAUDE_PLUGIN_ROOT}/lib/test-utils.sh"
run_tests
```

### レイヤードアーキテクチャ

```
plugin/
├── commands/          # ユーザーインターフェース層
├── agents/            # オーケストレーション層
├── skills/            # 知識層
└── lib/
    ├── core/          # コアロジック
    ├── integrations/  # 外部サービス連携
    └── utils/         # ヘルパー
```

大規模プラグイン（100ファイル超）・複数人開発で関心を分離したいとき。

### プラグイン内プラグイン

```
plugin/
├── core/              (commands/, agents/)
└── extensions/
    ├── extension-a/   (commands/, agents/)
    └── extension-b/   (commands/, agents/)
```

マニフェストで各パスを列挙する。モジュール化された機能・オプション機能・
プラグインファミリーに向く。

## ベストプラクティス

- **シンプルに始める**: フラット構成から始め、つらくなる前に再編する
- **関連するものをまとめる**: 無関係な機能を混ぜない
- **一貫したパターン**: プラグイン全体で同じ整理方針を貫く
- **ネストは浅く**: フォルダ階層が深いと発見に時間がかかる
- **構成を文書化**: README でフォルダ構成の意図を説明する
