# プラグイン設定ファイルのテンプレート集

## テンプレート: 基本設定

**.claude/my-plugin.local.md:**

```markdown
---
enabled: true
mode: standard
---

# My Plugin の設定

プラグインは標準モードで有効。
```

## テンプレート: 発展的な設定

```markdown
---
enabled: true
strict_mode: false
max_file_size: 1000000
allowed_extensions: [".js", ".ts", ".tsx"]
enable_logging: true
notification_level: info
retry_attempts: 3
timeout_seconds: 60
custom_path: "/path/to/data"
---

# My Plugin の詳細設定

このプロジェクトでは以下のカスタム設定を使う:
- 標準の検証モード
- 1MBのファイルサイズ上限
- JavaScript/TypeScriptファイルのみ許可
- infoレベルのログ
- 3回のリトライ

## 補足

この設定について質問があれば @team-lead へ。
```

## テンプレート: エージェント状態ファイル

**.claude/multi-agent-swarm.local.md:**

```markdown
---
agent_name: database-implementation
task_number: 4.2
pr_number: 5678
coordinator_session: team-leader
enabled: true
dependencies: ["Task 3.5", "Task 4.1"]
additional_instructions: "MySQLではなくPostgreSQLを使うこと"
---

# タスク割り当て: データベーススキーマの実装

新機能モジュールのデータベーススキーマを実装する。

## 要件

- マイグレーションファイルの作成
- 性能のためのインデックス追加
- 制約のテスト作成
- READMEへのスキーマ文書化

## 成功基準

- マイグレーションが正常に実行される
- 全テストがパスする
- CIグリーンでPRが作成される

## 協調

依存: Task 3.5（APIエンドポイント定義）、Task 4.1（データモデル設計）
状況はコーディネータセッション 'team-leader' に報告する。
```

## テンプレート: フィーチャーフラグ

**.claude/experimental-features.local.md:**

```markdown
---
enabled: true
features:
  - ai_suggestions
  - auto_formatting
  - advanced_refactoring
experimental_mode: false
---

# 実験的機能の設定

有効な機能: AI提案 / 自動フォーマット / 高度なリファクタリング
実験モードは OFF（安定機能のみ）。
```

## フックからの利用

```bash
# プラグインが設定されているか確認
if [[ ! -f ".claude/my-plugin.local.md" ]]; then
  exit 0  # 未設定。フックをスキップ
fi

# 設定を読む
FRONTMATTER=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' ".claude/my-plugin.local.md")
ENABLED=$(echo "$FRONTMATTER" | grep '^enabled:' | sed 's/enabled: *//')

# 設定を適用する
if [[ "$ENABLED" == "true" ]]; then
  : # フックが有効
fi
```

## gitignore

プロジェクトの `.gitignore` に必ず追加する:

```gitignore
# プラグイン設定（ユーザーローカル。コミットしない）
.claude/*.local.md
.claude/*.local.json
```

## 設定の編集

```bash
# 設定を編集する
vim .claude/my-plugin.local.md

# 変更は再起動後に反映される
exit    # Claude Code を終了
claude  # 再起動
```

フックはホットスワップできないため、変更には Claude Code の再起動が必要。
