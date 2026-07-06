---
description: ユーザーの希望に基づいてプラグイン設定ファイルを作成する
allowed-tools: ["Write", "AskUserQuestion"]
---

# プラグイン設定の作成

ユーザーが `.claude/my-plugin.local.md` 設定ファイルを作るのを支援する。

## 手順

### Step 1: ユーザーの希望を質問する

AskUserQuestion で設定を収集する:

```json
{
  "questions": [
    {
      "question": "このプロジェクトでプラグインを有効にしますか？",
      "header": "有効化",
      "multiSelect": false,
      "options": [
        { "label": "はい", "description": "プラグインが有効になる" },
        { "label": "いいえ", "description": "プラグインは無効のまま" }
      ]
    },
    {
      "question": "検証モードはどれにしますか？",
      "header": "モード",
      "multiSelect": false,
      "options": [
        { "label": "厳格", "description": "最大限の検証とセキュリティチェック" },
        { "label": "標準", "description": "バランスの取れた検証（推奨）" },
        { "label": "緩和", "description": "最小限の検証のみ" }
      ]
    }
  ]
}
```

### Step 2: 回答をパースする

- 質問1の回答: enabled（はい/いいえ）
- 質問2の回答: mode（strict / standard / lenient）

### Step 3: 設定ファイルを作成する

Write ツールで `.claude/my-plugin.local.md` を作成する:

```markdown
---
enabled: <「はい」ならtrue、「いいえ」ならfalse>
validation_mode: <strict / standard / lenient>
max_file_size: 1000000
notify_on_errors: true
---

# プラグイン設定

<モード>検証モードで設定されています。

設定を変更するには、このファイルを編集して Claude Code を再起動してください。
```

### Step 4: ユーザーに通知する

以下を伝える:

- 設定ファイルを `.claude/my-plugin.local.md` に作成したこと
- 現在の設定の要約
- 手動で編集する方法
- **変更の反映には Claude Code の再起動が必要**なこと
- 設定ファイルは gitignore 対象（コミットされない）であること

## 実装上の注意

書き込み前に必ずユーザー入力を検証する:

- mode が有効な値か確認する
- 数値フィールドが数値か検証する
- パスにトラバーサルがないか確認する
- 自由入力フィールドをサニタイズする
