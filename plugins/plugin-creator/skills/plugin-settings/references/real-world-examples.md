# 実プラグインの設定ファイル利用例

本番プラグインが `.claude/plugin-name.local.md` パターンをどう使っているかの
詳解。

## multi-agent-swarm プラグイン

### 設定ファイル

**.claude/multi-agent-swarm.local.md:**

```markdown
---
agent_name: auth-implementation
task_number: 3.5
pr_number: 1234
coordinator_session: team-leader
enabled: true
dependencies: ["Task 3.4"]
additional_instructions: "セッションではなくJWTトークンを使うこと"
---

# タスク: 認証の実装

REST API 向けの JWT ベース認証を構築する。

## 要件
- JWTトークンの生成と検証
- リフレッシュトークンのフロー
- 安全なパスワードハッシュ

## 成功基準
- 認証エンドポイントの実装
- テストがパス（カバレッジ100%）
- CIグリーンでPR作成
- ドキュメント更新

## 協調
Task 3.4（ユーザーモデル）に依存。
状況は 'team-leader' セッションに報告する。
```

### フックでの利用（agent-stop-notification.sh）

エージェントがアイドルになったらコーディネータに通知する Stop フック:

```bash
#!/bin/bash
set -euo pipefail

SWARM_STATE_FILE=".claude/multi-agent-swarm.local.md"

# スウォームが動いていなければ即終了
if [[ ! -f "$SWARM_STATE_FILE" ]]; then
  exit 0
fi

# frontmatter のパース
FRONTMATTER=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' "$SWARM_STATE_FILE")

# 設定の抽出
COORDINATOR_SESSION=$(echo "$FRONTMATTER" | grep '^coordinator_session:' | sed 's/coordinator_session: *//' | sed 's/^"\(.*\)"$/\1/')
AGENT_NAME=$(echo "$FRONTMATTER" | grep '^agent_name:' | sed 's/agent_name: *//' | sed 's/^"\(.*\)"$/\1/')
TASK_NUMBER=$(echo "$FRONTMATTER" | grep '^task_number:' | sed 's/task_number: *//' | sed 's/^"\(.*\)"$/\1/')
PR_NUMBER=$(echo "$FRONTMATTER" | grep '^pr_number:' | sed 's/pr_number: *//' | sed 's/^"\(.*\)"$/\1/')
ENABLED=$(echo "$FRONTMATTER" | grep '^enabled:' | sed 's/enabled: *//')

# 有効か確認
if [[ "$ENABLED" != "true" ]]; then
  exit 0
fi

# コーディネータに通知を送る
NOTIFICATION="🤖 エージェント ${AGENT_NAME}（Task ${TASK_NUMBER}, PR #${PR_NUMBER}）がアイドルです。"

if tmux has-session -t "$COORDINATOR_SESSION" 2>/dev/null; then
  tmux send-keys -t "$COORDINATOR_SESSION" "$NOTIFICATION" Enter
  sleep 0.5
  tmux send-keys -t "$COORDINATOR_SESSION" Enter
fi

exit 0
```

**主要パターン:** ①即終了（ファイルがなければ）②フィールド抽出
③enabled チェック ④設定に基づくアクション（coordinator_session への通知）。

### 作成と更新

スウォーム起動コマンドが heredoc で設定ファイルを生成し、
PR作成後に `sed` + アトミックな `mv` で `pr_number` を更新する。

## ralph-wiggum プラグイン

### 設定ファイル

**.claude/ralph-loop.local.md:**

```markdown
---
iteration: 1
max_iterations: 10
completion_promise: "全テストがパスしビルドが成功している"
started_at: "2026-07-05T14:30:00Z"
---

プロジェクトのリントエラーをすべて修正する。
修正のたびにテストがパスすることを確認する。
必要な変更は CLAUDE.md に記録する。
```

### フックでの利用（stop-hook.sh）

セッション終了を防ぎ、本文のプロンプトをループとして再投入する Stop フック:

```bash
#!/bin/bash
set -euo pipefail

RALPH_STATE_FILE=".claude/ralph-loop.local.md"

# ループが動いていなければ即終了
if [[ ! -f "$RALPH_STATE_FILE" ]]; then
  exit 0
fi

# frontmatter のパース
FRONTMATTER=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' "$RALPH_STATE_FILE")

ITERATION=$(echo "$FRONTMATTER" | grep '^iteration:' | sed 's/iteration: *//')
MAX_ITERATIONS=$(echo "$FRONTMATTER" | grep '^max_iterations:' | sed 's/max_iterations: *//')
COMPLETION_PROMISE=$(echo "$FRONTMATTER" | grep '^completion_promise:' | sed 's/completion_promise: *//' | sed 's/^"\(.*\)"$/\1/')

# 最大反復数のチェック
if [[ $MAX_ITERATIONS -gt 0 ]] && [[ $ITERATION -ge $MAX_ITERATIONS ]]; then
  echo "🛑 Ralphループ: 最大反復数 ($MAX_ITERATIONS) に到達。"
  rm "$RALPH_STATE_FILE"
  exit 0
fi

# トランスクリプトから完了宣言を確認
TRANSCRIPT_PATH=$(echo "$HOOK_INPUT" | jq -r '.transcript_path')
LAST_OUTPUT=$(grep '"role":"assistant"' "$TRANSCRIPT_PATH" | tail -1 | jq -r '.message.content | map(select(.type == "text")) | map(.text) | join("\n")')

if [[ "$COMPLETION_PROMISE" != "null" ]] && [[ -n "$COMPLETION_PROMISE" ]]; then
  PROMISE_TEXT=$(echo "$LAST_OUTPUT" | perl -0777 -pe 's/.*?<promise>(.*?)<\/promise>.*/$1/s; s/^\s+|\s+$//g')

  if [[ "$PROMISE_TEXT" = "$COMPLETION_PROMISE" ]]; then
    echo "✅ Ralphループ: 完了を検出"
    rm "$RALPH_STATE_FILE"
    exit 0
  fi
fi

# ループ継続 — 反復カウンタを増やす
NEXT_ITERATION=$((ITERATION + 1))

# マークダウン本文からプロンプトを抽出する
PROMPT_TEXT=$(awk '/^---$/{i++; next} i>=2' "$RALPH_STATE_FILE")

# 反復カウンタをアトミックに更新する
TEMP_FILE="${RALPH_STATE_FILE}.tmp.$$"
sed "s/^iteration: .*/iteration: $NEXT_ITERATION/" "$RALPH_STATE_FILE" > "$TEMP_FILE"
mv "$TEMP_FILE" "$RALPH_STATE_FILE"

# 終了をブロックし、プロンプトを再投入する
jq -n \
  --arg prompt "$PROMPT_TEXT" \
  --arg msg "🔄 Ralph 反復 $NEXT_ITERATION" \
  '{
    "decision": "block",
    "reason": $prompt,
    "systemMessage": $msg
  }'

exit 0
```

**主要パターン:** ①即終了 ②反復の追跡と上限の強制 ③出力内の完了シグナル
（`<promise>`）検出 ④本文を次のプロンプトとして抽出 ⑤アトミックな状態更新
⑥終了ブロックとプロンプト再投入。

## パターン比較

| 項目 | multi-agent-swarm | ralph-wiggum |
| --- | --- | --- |
| ファイル | `.claude/multi-agent-swarm.local.md` | `.claude/ralph-loop.local.md` |
| 目的 | エージェント協調の状態 | ループ反復の状態 |
| frontmatter | エージェントのメタデータ | ループ設定 |
| 本文 | タスク割り当て | ループさせるプロンプト |
| 更新 | PR番号・ステータス | 反復カウンタ |
| 削除 | 手動または完了時 | ループ終了時 |
| フック | Stop（通知） | Stop（ループ制御） |

## 実プラグインから学ぶベストプラクティス

1. **即終了パターン**: どちらも最初にファイル存在をチェックする
   （未設定時のエラー回避と高速化）
2. **enabled フラグ**: ファイルを消さずに一時的に無効化できる
3. **アトミック更新**: temp ファイル + `mv` で中断時の破損を防ぐ
4. **クォート処理**: YAMLのクォートあり/なし両方に対応する
5. **丁寧なエラー処理**: 欠損・破損ファイルでもクラッシュせず、
   必要ならクリーンアップして正常終了する

## アンチパターン

```bash
# ❌ パスのハードコード
FILE="/Users/alice/.claude/my-plugin.local.md"
# ✅ 相対パス
FILE=".claude/my-plugin.local.md"

# ❌ クォートなしの変数
echo $VALUE
# ✅ クォート付き
echo "$VALUE"

# ❌ 非アトミック更新（中断で破損の恐れ）
sed -i "s/field: .*/field: $VALUE/" "$FILE"
# ✅ アトミック
TEMP_FILE="${FILE}.tmp.$$"
sed "s/field: .*/field: $VALUE/" "$FILE" > "$TEMP_FILE"
mv "$TEMP_FILE" "$FILE"

# ❌ デフォルトなし（フィールド欠損で失敗）
if [[ $MAX -gt 100 ]]; then :; fi
# ✅ デフォルト付き
MAX=${MAX:-10}
```

## まとめ

`.claude/plugin-name.local.md` パターンの利点:

- シンプルで人間が読める設定
- バージョン管理と親和的（gitignore対象）
- プロジェクト単位の設定
- 標準的なbashツールで簡単にパースできる
- 構造化設定（YAML）と自由記述（マークダウン）の両立

ユーザー設定可能な挙動や状態の永続化が必要なプラグインには
このパターンを使う。
