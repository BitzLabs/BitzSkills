# プラグイン固有のコマンド機能リファレンス

Claude Code プラグインに同梱するコマンドに固有の機能とパターン。

## プラグインコマンドの発見

### 自動発見

```
plugin-name/
├── commands/              # 自動発見されるコマンド
│   ├── foo.md            # /foo (plugin:plugin-name)
│   └── bar.md            # /bar (plugin:plugin-name)
└── plugin.json
```

- プラグイン読み込み時に発見される（手動登録は不要）
- `/help` に「(plugin:plugin-name)」ラベル付きで表示される
- サブフォルダは名前空間になる

### 名前空間付きコマンド

```
commands/
├── review/
│   ├── security.md    # /security (plugin:plugin-name:review)
│   └── style.md       # /style (plugin:plugin-name:review)
└── deploy/
    ├── staging.md     # /staging (plugin:plugin-name:deploy)
    └── prod.md        # /prod (plugin:plugin-name:deploy)
```

コマンドが5個以上あるときの整理に使う。

### 命名規則

1. 説明的で行動指向の名前にする
2. 一般的な名前との衝突を避ける
3. 複数語はハイフンでつなぐ
4. 一意性のためプラグイン名プレフィックスを検討する

```
良い: /mylyn-sync, /analyze-performance, /docker-compose-up
避ける: /test（衝突しやすい）, /run（汎用的すぎ）, /do-stuff（説明不足）
```

## ${CLAUDE_PLUGIN_ROOT} 環境変数

プラグインのコマンド内で使える特殊な環境変数で、プラグインフォルダの
絶対パスに展開される。ポータブルなパス参照・スクリプト実行・複数ファイル
構成のプラグインに必須。

### 基本的な使い方

```markdown
---
description: プラグインスクリプトで分析する
allowed-tools: Bash(node:*), Read
---

分析を実行: !`node ${CLAUDE_PLUGIN_ROOT}/scripts/analyze.js`

テンプレートを読む: @${CLAUDE_PLUGIN_ROOT}/templates/report.md
```

### よくあるパターン

```markdown
# 1. プラグインスクリプトの実行
リント結果: !`node ${CLAUDE_PLUGIN_ROOT}/bin/lint.js $1`

# 2. 設定ファイルの読み込み
設定: @${CLAUDE_PLUGIN_ROOT}/config/deploy-config.json

# 3. リソースへのアクセス
テンプレート: @${CLAUDE_PLUGIN_ROOT}/templates/api-report.md

# 4. 多段ワークフロー
Step 1 - 準備: !`bash ${CLAUDE_PLUGIN_ROOT}/scripts/prepare.sh $1`
Step 2 - 設定: @${CLAUDE_PLUGIN_ROOT}/config/$1.json
Step 3 - 実行: !`${CLAUDE_PLUGIN_ROOT}/bin/execute $1`
```

### ベストプラクティス

1. **プラグイン内パスには必ず使う**: `@./templates/foo.md` は作業ディレクトリ
   基準になってしまうので不可
2. **ファイル存在を検証する**:
   `!`test -f ${CLAUDE_PLUGIN_ROOT}/config.json && echo "exists" || echo "missing"``
3. **プラグイン構造をコメントで文書化する**（HTMLコメントで構成を書いておく）
4. **引数と組み合わせる**: `!`${CLAUDE_PLUGIN_ROOT}/bin/process.sh $1 $2``

### トラブルシューティング

- **変数が展開されない**: コマンドがプラグインから読み込まれているか、
  bash実行が許可されているか、構文が正確に `${CLAUDE_PLUGIN_ROOT}` かを確認
- **file not found**: プラグイン内の実在パスか、パーミッションを確認
- **パスに空白**: 特別なクォートは不要（自動処理される）

## プラグインコマンドのパターン

### パターン1: 設定ベース

呼び出しごとに一貫した設定が必要なコマンド:

```markdown
---
description: プラグイン設定でデプロイする
allowed-tools: Read, Bash(*)
---

設定を読み込む: @${CLAUDE_PLUGIN_ROOT}/deploy-config.json

$1 環境へ以下を使ってデプロイする:
1. 上記の設定
2. 現在のブランチ: !`git branch --show-current`
3. アプリのバージョン: !`cat package.json | grep version`
```

### パターン2: テンプレートベース生成

標準化された成果物の生成:

```markdown
---
description: テンプレートからドキュメントを生成する
argument-hint: [component-name]
---

テンプレート: @${CLAUDE_PLUGIN_ROOT}/templates/component-docs.md

$1 コンポーネントのドキュメントをテンプレート構造に従って生成する。
```

### パターン3: 複数スクリプトのワークフロー

```markdown
---
description: ビルドとテストの一括ワークフロー
allowed-tools: Bash(*)
---

ビルド: !`bash ${CLAUDE_PLUGIN_ROOT}/scripts/build.sh`
検証: !`bash ${CLAUDE_PLUGIN_ROOT}/scripts/validate.sh`
テスト: !`bash ${CLAUDE_PLUGIN_ROOT}/scripts/test.sh`

全出力をレビューし、ビルド状況・検証結果・テスト結果・次のステップを報告する。
```

### パターン4: 環境対応コマンド

```markdown
---
description: 環境に応じてデプロイする
argument-hint: [dev|staging|prod]
---

環境設定: @${CLAUDE_PLUGIN_ROOT}/config/$1.json

$1 環境の設定でアプリケーションをデプロイし、スモークテストを実行する。
```

### パターン5: プラグインデータ管理

```markdown
---
description: 分析結果をプラグインのキャッシュに保存する
allowed-tools: Bash(*), Read, Write
---

キャッシュ先: ${CLAUDE_PLUGIN_ROOT}/cache/

@$1 を分析し、結果をキャッシュに保存する:
!`mkdir -p ${CLAUDE_PLUGIN_ROOT}/cache && date > ${CLAUDE_PLUGIN_ROOT}/cache/last-run.txt`
```

## プラグインコンポーネントとの統合

### エージェント起動

```markdown
---
description: プラグインエージェントで深い分析を行う
argument-hint: [file-path]
---

@$1 の詳細なコード分析を code-analyzer エージェントで開始する。

エージェントは以下を行う:
1. コード構造の分析
2. パターンの特定
3. 改善の提案
4. 詳細レポートの生成
```

エージェントはプラグインの `agents/` に定義されている必要がある。
Claude が Task ツールで自動的に起動する。

### スキル利用

```markdown
---
description: 規約に従ってAPIをドキュメント化する
argument-hint: [api-file]
---

@$1 のAPIを、api-docs-standards スキルを使って以下を含むように
ドキュメント化する: エンドポイント説明・パラメータ仕様・レスポンス形式・
エラーコード・使用例。
```

スキル名に言及することで Claude にスキルの読み込みを促す。

### フックとの協調

```markdown
---
description: pre-commit検証付きでコミットする
allowed-tools: Bash(git:*)
---

ステージング: !`git add $1`
コミット: !`git commit -m "$2"`

注: このコミットはプラグインの pre-commit フックを起動する。
フックの出力を確認し、問題があれば対処する。
```

### 複数コンポーネントの統合

```markdown
---
description: 包括的なコードレビューワークフロー
argument-hint: [file-path]
---

レビュー対象: @$1

1. **静的解析**（プラグインスクリプト）
   !`node ${CLAUDE_PLUGIN_ROOT}/scripts/lint.js $1`

2. **詳細レビュー**（プラグインエージェント）
   code-reviewer エージェントを起動する。

3. **規約チェック**（プラグインスキル）
   code-standards スキルで準拠を確認する。

4. **レポート**（プラグインテンプレート）
   テンプレート: @${CLAUDE_PLUGIN_ROOT}/templates/review-report.md

全出力を統合した最終レポートを生成する。
```

## バリデーションパターン

### 入力検証

```markdown
環境の検証: !`echo "$1" | grep -E "^(dev|staging|prod)$" || echo "INVALID"`

$1 が dev / staging / prod のいずれかなら検証済み設定でデプロイする。
そうでなければ「無効な環境 '$1'。dev / staging / prod のいずれかを指定」と
エラーを説明する。
```

### ファイル存在チェック

```markdown
ファイル確認: !`test -f $1 && echo "EXISTS" || echo "MISSING"`

存在すれば処理する: @$1
なければ、期待される場所・必要な形式・作り方を説明する。
```

### 必須引数の検証

```markdown
入力検証: !`test -n "$1" -a -n "$2" && echo "OK" || echo "MISSING"`

両方あれば: バージョン $2 を $1 環境へデプロイする
なければ: 「環境とバージョンの両方が必要。使い方: /deploy [env] [version]」
```

### プラグインリソースの検証

```markdown
プラグイン構成の検証:
- 設定: !`test -f ${CLAUDE_PLUGIN_ROOT}/config.json && echo "✓" || echo "✗"`
- スクリプト: !`test -d ${CLAUDE_PLUGIN_ROOT}/scripts && echo "✓" || echo "✗"`
- 実行ファイル: !`test -x ${CLAUDE_PLUGIN_ROOT}/bin/analyze && echo "✓" || echo "✗"`

全チェックがパスすれば分析に進む。
失敗があれば不足コンポーネントと導入手順を報告する。
```

### エラーの丁寧な処理

```markdown
処理を試行: !`node ${CLAUDE_PLUGIN_ROOT}/scripts/process.js $1 2>&1 || echo "ERROR: $?"`

成功時: 結果を報告し、次のステップを提案する。
失敗時: 考えられる原因・トラブルシューティング手順・代替アプローチを提示する。
```

## ベストプラクティスまとめ

1. **プラグイン内パスには必ず `${CLAUDE_PLUGIN_ROOT}`** を使う
2. **入力は早めに検証**する（必須引数・ファイル存在・形式）
3. **プラグイン構造を文書化**する（必要ファイル・スクリプトの目的・依存）
4. **他コンポーネントと統合**する（複雑なタスクはエージェント、専門知識は
   スキル、イベント処理はフック）
5. **役に立つエラーメッセージ**を出す（何が起きたか・直し方・代替案）
6. **エッジケースを処理**する（ファイル欠落・無効引数・スクリプト失敗）
7. **コマンドは焦点を絞る**（1コマンド1目的。複雑なロジックはスクリプトへ）
8. **複数の環境でテスト**する
