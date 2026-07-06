# 発展的なワークフローパターン

複数ステップのコマンド連鎖と、複雑なワークフローを組み立てる合成パターン。

## 概要

発展的なワークフローは、複数のコマンドを組み合わせ、呼び出しをまたいで
状態を管理し、洗練された自動化シーケンスを作る。単純なコマンドを部品として
複雑な機能を構築できる。

## 複数ステップのパターン

### 順次ワークフロー

ユーザーを複数ステップの手順に沿って導くコマンド:

```markdown
---
description: PRレビューの一括ワークフロー
argument-hint: [pr-number]
allowed-tools: Bash(gh:*), Read, Grep
---

# PR #$1 のレビューワークフロー

## Step 1: PR詳細の取得
!`gh pr view $1 --json title,body,author,files`

## Step 2: ファイルレビュー
変更ファイル: !`gh pr diff $1 --name-only`

各ファイルについて: コード品質・テストの有無・ドキュメントを確認する。

## Step 3: チェックの実行
テスト状況: !`gh pr checks $1`

全テストのパス・コンフリクトの有無・CI/CDの成功を確認する。

## Step 4: フィードバック

問題点（重大/軽微）・改善提案・承認可否をまとめ、
「承認 / 変更依頼 / コメントのみ」のどれにするかユーザーに確認する。
```

**特徴**: 番号付きステップ、bash実行によるコンテキスト、ユーザーの判断ポイント、
次アクションの提案。

### 状態を持ち回るワークフロー

呼び出し間で状態を保持するコマンド群。初期化コマンドが
`.claude/deployment-state.local.md` に YAML frontmatter 付きで状態を書き:

```yaml
---
workflow: deployment
stage: initialized
branch: feature/new-api
commit: abc123def
timestamp: 2026-07-05T10:30:00Z
---
```

後続コマンド（`/deploy-test` → `/deploy-build` → `/deploy-execute`）が
状態ファイルを読んで次のステップを判断し、stage を更新していく。

**利点**: コマンド間での永続状態、明確な進行、安全なチェックポイント、
中断からの再開。

### 条件分岐ワークフロー

```markdown
---
description: スマートなデプロイワークフロー
argument-hint: [environment]
allowed-tools: Bash(git:*), Bash(npm:*), Read
---

# $1 へのデプロイ

## 事前チェック

ブランチ: !`git branch --show-current`
状態: !`git status --short`

**条件の判定:**

1. ブランチ: main/master なら承認必須、feature なら警告、hotfix なら短縮フロー
2. テスト: !`npm test` — 失敗なら停止して修正を優先、成功なら続行
3. 環境: production なら追加検証、staging なら標準、dev なら最小チェック

判定結果に基づいたワークフローで進める。実行前にユーザーへ確認する。
```

## コマンド合成パターン

### コマンドチェーン

単機能コマンド（`/format-code` / `/lint-code` / `/test-all`）を、
メタコマンドがオーケストレーションする:

```markdown
---
description: コードレビューの準備
---

# レビュー準備シーケンス

1. フォーマット: /format-code
2. リント: /lint-code
3. テスト: /test-all
4. カバレッジ: /coverage-report

各ステップの完了後、結果をまとめてレビュー資料を作成する。
```

### パイプライン

前のコマンドの出力を処理するコマンド:

```markdown
---
description: テスト失敗の分析
---

# テスト失敗の分析

1. テスト結果を読む（未実行なら /test-all を先に）
2. 失敗を分類する（フレーキー / 恒常的 / 新規 vs 既存）
3. 優先度付け（影響度 × 頻度 × 修正の手間）
4. 修正計画を作る（原因仮説・修正方針・見積り）

「最優先の失敗を修正 / 全件の修正計画 / issue化」のどれにするか確認する。
```

### 並列実行

```markdown
---
description: 包括的な検証を並列実行する
allowed-tools: Bash(*), Read
---

以下を並列で開始する:
- コード品質チェック
- セキュリティスキャン
- 依存関係監査
- パフォーマンスプロファイリング

各プロセスを監視し、全完了後にサマリー
（品質: PASS / セキュリティ: WARN 2件 / …）と詳細を報告する。
```

## ワークフロー状態管理

### .local.md ファイルの利用

プラグイン固有の状態ファイルに保存する:

```markdown
.claude/plugin-name-workflow.local.md:

---
workflow: deployment
stage: testing
started: 2026-07-05T10:30:00Z
environment: staging
tests_passed: false
---

# デプロイワークフロー状態

完了: ✅ 検証 / ✅ ブランチ確認 / ⏳ テスト（進行中）
残り: ビルド / デプロイ / スモークテスト
```

コマンド内では `@.claude/plugin-name-workflow.local.md` で読み込み、
frontmatter をパースして次のステップを決める。

### 中断からの復旧

```markdown
---
description: デプロイワークフローを再開する
allowed-tools: Read
---

中断されたワークフローを確認する:
状態ファイル: @.claude/plugin-name-workflow.local.md

見つかったら開始時刻・環境・最後に完了したステップを提示し、
「最後のステップから再開 / 最初からやり直し / 中止してクリーンアップ」を
ユーザーに選ばせる。
```

### コマンド間シグナル

フラグファイルでコマンド同士が通信する:

```markdown
# /mark-feature-complete が .claude/feature-complete.flag を作成
# 他のコマンド（/integration-test, /release-notes 等）がフラグを検出して
# 挙動を変える
```

### ワークフローのロック

同時実行を防止する:

```markdown
.claude/deployment.lock が存在すれば:
  「デプロイが既に進行中（開始: ロックファイルの時刻）。
   完了を待つか /deployment-abort を実行」と伝えて終了する。

存在しなければロックを作成してデプロイを進め、
完了コマンドでロックを削除する。
```

## 発展的な引数処理

```markdown
# デフォルト値付きの任意引数
環境: ${1:-staging} / バージョン: ${2:-latest}

# 引数の検証
valid_envs="dev staging production" に $1 が含まれなければ
有効な選択肢を提示して終了する。

# 引数の変換（省略形の展開）
d/dev → development, s/stg → staging, p/prod → production
```

## エラーハンドリング

### 丁寧な失敗

```markdown
## Step 1: テスト
!`npm test`

失敗したら:
  「1. 修正して再試行 / 2. テストをスキップ（非推奨）/ 3. 中止」を
  ユーザーに確認し、入力を待ってから続行する。

## Step 2: ビルド
（Step 1 が成功した場合のみ続行）
```

### 失敗時ロールバック

```markdown
ロールバック用に現在の状態を保存: !`current-version.sh`
新バージョンをデプロイ: !`deploy.sh`

失敗したら自動ロールバック（!`rollback.sh`）を実行し、
前バージョンへ戻したことと失敗ログの場所を報告する。
```

### チェックポイント復旧

各ステージ完了時に `.claude/deployment-checkpoints.log` へ記録し、
失敗時は `/deployment-resume [最後の成功チェックポイント]` で再開する。

## ベストプラクティス

**ワークフロー設計:**

1. 明確な進行（ステップに番号を付け、現在位置を示す）
2. 明示的な状態（暗黙の状態に依存しない）
3. ユーザーの制御（判断ポイントを設ける）
4. エラー復旧（失敗を丁寧に処理する）
5. 進捗表示（完了と残りを示す）

**コマンド合成:**

1. 単一責務（各コマンドは1つのことをうまくやる）
2. 合成可能な設計（コマンド同士が組み合わせやすい）
3. 標準インターフェース（入出力形式の一貫性）
4. 疎結合（互いの内部実装に依存しない）

**状態管理:**

1. `.local.md` ファイルで永続化する
2. 状態ファイルはアトミックに書く
3. 読み込み時に形式・完全性を検証する
4. 古い状態ファイルは掃除する
5. 状態ファイルの形式を文書化する
