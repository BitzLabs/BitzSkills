# コマンド frontmatter リファレンス

スラッシュコマンドの YAML frontmatter 全フィールドの詳細リファレンス。

## 概要

frontmatter はコマンドファイル先頭の任意メタデータ。**全フィールドが任意**で、
frontmatter なしでもコマンドは動作する。

```markdown
---
description: 簡潔な説明
allowed-tools: Read, Write
model: sonnet
argument-hint: [arg1] [arg2]
---

コマンドのプロンプト本文...
```

## フィールド仕様

### description

**型**: 文字列 / **省略時**: プロンプトの先頭行 / **推奨長**: 60文字以内

`/help` に表示される説明。動詞から始め、具体的に書く。

- ✅ 「PRのコード品質とセキュリティをレビューする」
- ✅ 「指定環境へアプリケーションをデプロイする」
- ❌ 「このコマンドはPRをレビューします」（「このコマンドは」が冗長）
- ❌ 「レビュー」（曖昧すぎる）

### allowed-tools

**型**: 文字列または配列 / **省略時**: 会話の権限を継承

コマンドが使えるツールを制限・指定する。

```yaml
# カンマ区切り
allowed-tools: Read, Write, Edit

# 配列
allowed-tools:
  - Read
  - Bash(git:*)
```

**Bashのコマンドフィルタ**:

```yaml
allowed-tools: Bash(git:*)     # gitコマンドのみ
allowed-tools: Bash(npm:*)     # npmコマンドのみ
allowed-tools: "*"             # 全ツール（非推奨）
```

**使いどころ**:

1. **セキュリティ**: 読み取り専用コマンドは `Read, Grep` に絞る
2. **明示**: 必要なツールをドキュメントとして示す
3. **bash実行**: インラインbash（`!` 構文）を使うときに必要

できるだけ制限的に指定し、Bash は必ずコマンドフィルタ付きで使う。

### model

**型**: 文字列（`sonnet` / `opus` / `haiku`） / **省略時**: 会話のモデルを継承

| 値 | 適する場面 |
| --- | --- |
| `haiku` | 単純・定型的なコマンド。高速実行・高頻度呼び出し |
| `sonnet` | 標準的なワークフロー（既定の選択肢） |
| `opus` | 複雑な分析・アーキテクチャ判断・深いコード理解 |

特別な理由がなければ省略する。

### argument-hint

**型**: 文字列 / **省略時**: なし

引数の補完ヒント・ドキュメント。各引数を `[]` で囲み、説明的な名前を使う。

```yaml
argument-hint: [pr-number]
argument-hint: [environment] [version]
argument-hint: [source-branch] [target-branch] [commit-message]
```

- `[arg1]` のような無意味な名前は避ける
- 本文の位置引数（`$1` `$2`）と順序を一致させる

### disable-model-invocation

**型**: 真偽値 / **省略時**: `false`

`true` にすると SlashCommand ツールからのプログラム的呼び出しを禁止し、
ユーザーが手で `/command` と打ったときだけ実行される。

**使いどころ**:

1. **人間の判断が必要なコマンド**（本番デプロイ承認など）
2. **破壊的操作**（テストデータ全削除など）
3. **対話的ウィザード**（ユーザー入力が必須のフロー）

Claude の自律性を制限するので、必要な場合だけ控えめに使う。

## 完全な例

### 最小（frontmatterなし）

```markdown
このコードの一般的な問題をレビューし、改善を提案する。
```

### 標準

```markdown
---
description: Gitの変更をレビューする
allowed-tools: Bash(git:*), Read
---

現在の変更: !`git diff --name-only`

変更された各ファイルをコード品質・バグ・ベストプラクティスの観点でレビューする。
```

### 複合

```markdown
---
description: アプリケーションを環境へデプロイする
argument-hint: [app-name] [environment] [version]
allowed-tools: Bash(kubectl:*), Bash(helm:*), Read
model: sonnet
---

$1 をバージョン $3 で $2 環境へデプロイする。

デプロイ前チェック:
- $2 の設定を確認する
- クラスタ状態: !`kubectl cluster-info`
- バージョン $3 の存在を検証する
```

### 手動専用

```markdown
---
description: 本番デプロイを承認する
argument-hint: [deployment-id]
disable-model-invocation: true
allowed-tools: Bash(gh:*)
---

<!--
手動承認必須。人間の判断が必要なため自動化できない。
-->

デプロイ $1 の本番承認レビューを行う:

デプロイ詳細: !`gh api /deployments/$1`

全テストのパス・セキュリティスキャン・ステークホルダー承認・
ロールバック計画を確認する。
```

## バリデーション

### よくあるエラー

| エラー | 修正 |
| --- | --- |
| YAML構文エラー（クォート閉じ忘れ等） | YAMLとしてパース確認する |
| `allowed-tools: Bash`（フィルタなし） | `Bash(git:*)` 形式にする |
| `model: gpt4`（無効なモデル名） | `sonnet` / `opus` / `haiku` にする |

### チェックリスト

- [ ] YAML構文が正しい
- [ ] description が60文字以内
- [ ] allowed-tools の形式が正しい
- [ ] model が有効な値
- [ ] argument-hint が本文の位置引数と一致
- [ ] disable-model-invocation の使用が妥当

## まとめ

1. **最小から始める**: frontmatter は必要になってから足す
2. **引数は必ず文書化**: 引数があれば argument-hint を付ける
3. **ツールは最小権限**: 動く範囲で最も制限的に
4. **モデルは適材適所**: 速度なら haiku、複雑さなら opus
5. **手動専用は控えめに**: 本当に必要なときだけ
