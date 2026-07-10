# コマンドの文書化パターン

自己文書化された、保守しやすいコマンドを作るための戦略。

## 概要

よく文書化されたコマンドは使いやすく、保守しやすく、配布しやすい。
ドキュメントはコマンド自体に埋め込み、ユーザーと保守者がすぐ参照できる
ようにする。

## 自己文書化コマンドの構造

### 完全なテンプレート

```markdown
---
description: 60文字以内の明確で実行的な説明
argument-hint: [arg1] [arg2] [optional-arg]
allowed-tools: Read, Bash(git:*)
model: sonnet
---

<!--
COMMAND: command-name
VERSION: 1.0.0
AUTHOR: チーム名
LAST UPDATED: 2026-07-05

PURPOSE:
このコマンドが何をするか、なぜ存在するかの詳細な説明。

USAGE:
  /command-name arg1 arg2

ARGUMENTS:
  arg1: 第1引数の説明（必須）
  arg2: 第2引数の説明（任意、既定値 X）

EXAMPLES:
  /command-name feature-branch main
    → feature-branch を main と比較する

REQUIREMENTS:
  - Gitリポジトリであること
  - 対象ブランチが存在すること

RELATED COMMANDS:
  /other-command - 関連機能

TROUBLESHOOTING:
  - ブランチが見つからない: 名前の綴りを確認
  - permission denied: リポジトリのアクセス権を確認

CHANGELOG:
  v1.0.0 (2026-07-05): 初回リリース
-->

# コマンド実装

[プロンプト本文...]
```

### コメントセクションの役割

| セクション | 内容 |
| --- | --- |
| PURPOSE | 解決する問題・ユースケース・使うべき/使うべきでない場面 |
| USAGE | 呼び出しパターン・必須/任意引数・既定値 |
| ARGUMENTS | 各引数の説明・型・有効な値の範囲 |
| EXAMPLES | 典型的な使い方・エッジケース・期待される出力 |
| REQUIREMENTS | 依存ツール・権限・環境の前提 |
| RELATED COMMANDS | 類似・補完・代替のコマンド |
| TROUBLESHOOTING | 既知の問題と解決策 |
| CHANGELOG | いつ何が変わったか。破壊的変更は明示 |

## インライン文書化

### セクションコメント

```markdown
<!-- SECTION 1: 検証 -->
<!-- 続行前に前提条件をチェックする -->

前提条件を確認中...

<!-- SECTION 2: 分析 -->
<!-- ブランチ間の差分を分析する -->

$1 と $2 の差分を分析中...
```

### 判断ポイントの文書化

```markdown
<!-- 判断ポイント: ユーザーが設定を確認する -->
<!-- デプロイはリスクがあるため自動続行しない -->

上記の設定を確認する。

**デプロイを続行しますか？**
- 「yes」で続行 / 「no」で中止 / 「edit」で設定変更

[ユーザー入力を待ってから続行する]
```

## ヘルプの組み込み

### help サブコマンド

```markdown
---
description: help付きのメインコマンド
argument-hint: [subcommand] [args]
---

$1 が「help」「--help」「-h」なら以下を表示して終了する:

  USAGE: /command [subcommand] [args]

  SUBCOMMANDS:
    init [name]   新しい設定を初期化
    deploy [env]  環境へデプロイ
    status        現在の状態を表示
    rollback      直前のデプロイを巻き戻し
    help          このヘルプを表示

[通常のコマンド処理...]
```

### 文脈依存のヘルプ

引数なしで呼ばれたら、使用可能な操作の一覧と使用例を示して終了する。

## エラーメッセージの文書化

### 役立つエラーメッセージ

```markdown
$1 が空なら:
  ❌ エラー: 必須引数がありません

  「file-path」引数が必須です。
  USAGE: /validate [file-path]
  EXAMPLE: /validate src/app.js

$1 が存在しないファイルなら:
  ❌ エラー: ファイルが見つかりません: $1

  よくある原因:
  1. パスの誤字
  2. ファイルが削除・移動された
  3. 権限不足

  確認方法:
  - 綴りを確認: $1
  - 存在確認: ls -la $(dirname "$1")
```

### 復旧手順の案内

失敗時には「何が起きたか / それが何を意味するか / 復旧ステップ」を提示する:

```markdown
❌ 操作失敗

何が起きたか: スクリプトが非ゼロの終了コードを返した。
影響: 変更が部分適用され、状態が不整合の可能性がある。

復旧ステップ:
1. ログ確認: cat /tmp/operation.log
2. 状態確認: /check-state
3. 必要なら巻き戻し: /rollback-operation
4. 原因を修正して再試行: /retry-operation
```

## 使用例の文書化

例を先に見せてから説明する（example-driven）:

```markdown
# 変換コマンド

## まず例から

### 例1: JSON → YAML
コマンド: /transform data.json yaml
入力 {"name": "test"} → 出力 name: test

### 例2: CSV → JSON
コマンド: /transform data.csv json

### 例3: オプション付き
コマンド: /transform data.json yaml --pretty --sort-keys

---

## あなたの変換

ファイル: $1 / 形式: $2
[変換を実行...]
```

## 保守用ドキュメント

### バージョンと変更履歴

```markdown
<!--
VERSION: 2.1.0

CHANGELOG:
  v2.1.0 (2026-07-05):
    - YAML設定のサポートを追加
    - エラーメッセージを改善
  v2.0.0 (2026-06-01):
    - 破壊的変更: 引数の順序を変更
    - 移行ガイド: /migration-v2

DEPRECATION WARNINGS:
  - --legacy-mode は v2.1.0 で非推奨。v3.0.0 で削除予定。--modern-mode を使う

KNOWN ISSUES:
  - #123: 大きいファイルで低速（回避策: --stream フラグ）
-->
```

### 保守メモ

```markdown
<!--
MAINTENANCE NOTES:

DEPENDENCIES: git 2.x以降、jq、bash 4.0+
PERFORMANCE: 1MB未満は高速パス。大きいファイルはストリーム処理
SECURITY: 全入力を検証。allowed-toolsでBashを制限。認証情報は含めない
TESTING: tests/command-test.sh、tests/integration/
FUTURE: TODO: TOML対応、並列処理
-->
```

## README

複雑なコマンド群にはプラグインの README で以下を提供する:
インストール方法・基本的な使い方・引数一覧・例・設定ファイル
（`.claude/command-name.local.md`）・要件・トラブルシューティング。

## ベストプラクティス

**原則:**

1. **未来の自分のために書く**: 詳細は忘れる前提で
2. **説明より先に例**: 見せてから語る
3. **段階的開示**: 基本を先に、詳細は参照可能に
4. **常に最新**: コードを変えたらドキュメントも更新
5. **例を検証**: 書いた例が実際に動くことを確認

**置き場所:**

1. コマンドファイル内: 基本的な使い方・例・インライン説明
2. README: インストール・設定・トラブルシューティング
3. 別ドキュメント: 詳細ガイド・チュートリアル
4. コメント: 保守者向けの実装詳細

**スタイル:**

能動態・一貫した用語・見出しとリストとコードブロックで整形・
初心者にもわかる書き方。

## チェックリスト

- [ ] frontmatter の description が明確
- [ ] argument-hint が全引数を文書化
- [ ] コメントに使用例がある
- [ ] エラーメッセージが役立つ
- [ ] 要件が文書化されている
- [ ] 関連コマンドが列挙されている
- [ ] CHANGELOG が維持されている
- [ ] 例が実際に動く
