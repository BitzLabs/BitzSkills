# 発展的なフックのユースケース

高度な自動化ワークフローのためのフックパターンとテクニック。

## 多段検証

コマンドフックとプロンプトフックを重ねて多層検証する:

```json
{
  "PreToolUse": [
    {
      "matcher": "Bash",
      "hooks": [
        {
          "type": "command",
          "command": "bash ${CLAUDE_PLUGIN_ROOT}/scripts/quick-check.sh",
          "timeout": 5
        },
        {
          "type": "prompt",
          "prompt": "bashコマンドの詳細分析: $TOOL_INPUT",
          "timeout": 15
        }
      ]
    }
  ]
}
```

コマンドフックが明らかに安全なコマンドを高速承認し、
プロンプトフックがそれ以外を分析する。

## 条件付き実行

環境やコンテキストに応じてフックを実行する:

```bash
#!/bin/bash
# CI環境でのみ実行する
if [ -z "$CI" ]; then
  echo '{"continue": true}' # CI以外ではスキップ
  exit 0
fi

# CIでの検証ロジック
input=$(cat)
# ... 検証コード ...
```

**用途:** CI とローカルでの挙動の切り替え、プロジェクト別の検証、
ユーザー別のルール。

## 状態によるフックの連携

一時ファイルでフック間の状態を共有する:

```bash
# フック1（PreToolUse）: 分析して状態を保存する
risk_level=$(calculate_risk "$command")
echo "$risk_level" > /tmp/hook-state-$$
```

```bash
# フック2（PostToolUse）: 保存された状態を使う
risk_level=$(cat /tmp/hook-state-$$ 2>/dev/null || echo "unknown")

if [ "$risk_level" = "high" ]; then
  echo "高リスク操作を検出" >&2
  exit 2
fi
```

**重要:** これは**順序のあるイベント間**（PreToolUse → PostToolUse 等）
でのみ機能する。同一イベント内の並列フック間では使えない。

## 動的なフック設定

プロジェクト設定に応じてフックの挙動を変える:

```bash
#!/bin/bash
cd "$CLAUDE_PROJECT_DIR" || exit 1

# プロジェクト固有の設定を読む
if [ -f ".claude-hooks-config.json" ]; then
  strict_mode=$(jq -r '.strict_mode' .claude-hooks-config.json)

  if [ "$strict_mode" = "true" ]; then
    : # 厳格な検証を適用する
  else
    : # 緩やかな検証を適用する
  fi
fi
```

## コンテキスト対応プロンプトフック

トランスクリプトとセッションの文脈を使って賢く判断する:

```json
{
  "Stop": [
    {
      "matcher": "*",
      "hooks": [
        {
          "type": "prompt",
          "prompt": "$TRANSCRIPT_PATH のトランスクリプト全体をレビューする。確認: 1) コード変更後にテストが実行されたか 2) ビルドは成功したか 3) ユーザーの質問すべてに答えたか 4) 未完了の作業はないか。すべて完了している場合のみ 'approve' を返す。"
        }
      ]
    }
  ]
}
```

## パフォーマンス最適化

### 検証結果のキャッシュ

```bash
#!/bin/bash
input=$(cat)
file_path=$(echo "$input" | jq -r '.tool_input.file_path')
cache_key=$(echo -n "$file_path" | md5sum | cut -d' ' -f1)
cache_file="/tmp/hook-cache-$cache_key"

# キャッシュの確認（5分間有効）
if [ -f "$cache_file" ]; then
  cache_age=$(($(date +%s) - $(stat -c%Y "$cache_file")))
  if [ "$cache_age" -lt 300 ]; then
    cat "$cache_file"
    exit 0
  fi
fi

# 検証を実施してキャッシュする
result='{"decision": "approve"}'
echo "$result" > "$cache_file"
echo "$result"
```

### 並列実行の活用

フックは並列実行されるので、独立した小さいフックに分割すると
合計レイテンシが下がる（サイズチェック / パスチェック / 内容の安全性を
それぞれ別フックにする等）。

## イベント横断のワークフロー

**SessionStart** でトラッキングを初期化し、**PostToolUse** でイベントを
記録し、**Stop** で記録に基づいて検証する:

```bash
# SessionStart: カウンタの初期化
echo "0" > /tmp/test-count-$$

# PostToolUse: テスト実行を記録
if [[ "$command" == *"test"* ]]; then
  count=$(cat /tmp/test-count-$$ 2>/dev/null || echo "0")
  echo $((count + 1)) > /tmp/test-count-$$
fi

# Stop: 記録に基づく検証
test_count=$(cat /tmp/test-count-$$ 2>/dev/null || echo "0")
if [ "$test_count" -eq 0 ]; then
  echo '{"decision": "block", "reason": "テストが実行されていません"}' >&2
  exit 2
fi
```

## 外部システム統合

```bash
# Slack通知
curl -X POST "$SLACK_WEBHOOK" \
  -H 'Content-Type: application/json' \
  -d "{\"text\": \"フックが ${tool_name} 操作をブロックしました\"}" \
  2>/dev/null

# データベースへのログ
psql "$DATABASE_URL" -c "INSERT INTO hook_logs (event, data) VALUES ('PreToolUse', '$input')" 2>/dev/null

# メトリクス収集（statsd）
echo "hook.pretooluse.${tool_name}:1|c" | nc -u -w1 statsd.local 8125
```

## セキュリティパターン

### レート制限

分単位でコマンド頻度を記録し、閾値超過で拒否する:

```bash
if [ "$count" -gt 10 ]; then
  echo '{"decision": "deny", "reason": "レート制限を超過しました"}' >&2
  exit 2
fi
```

### 監査ログ

```bash
timestamp=$(date -Iseconds)
echo "$timestamp | $USER | $tool_name | $input" >> ~/.claude/audit.log
```

### 秘密情報の検出

```bash
content=$(echo "$input" | jq -r '.tool_input.content')

# 代表的な秘密情報パターンをチェックする
if echo "$content" | grep -qE "(api[_-]?key|password|secret|token).{0,20}['\"]?[A-Za-z0-9]{20,}"; then
  echo '{"decision": "deny", "reason": "コンテンツに秘密情報の可能性を検出"}' >&2
  exit 2
fi
```

## 発展フックのテスト

```bash
# ユニットテストの例
# Test 1: 安全なコマンドを承認する
echo '{"tool_input": {"command": "ls"}}' | bash validate-bash.sh
[ $? -eq 0 ] && echo "✓ Test 1 パス"

# Test 2: 危険なコマンドをブロックする
echo '{"tool_input": {"command": "rm -rf /"}}' | bash validate-bash.sh
[ $? -eq 2 ] && echo "✓ Test 2 パス"
```

統合テストでは `CLAUDE_PROJECT_DIR` / `CLAUDE_PLUGIN_ROOT` をテスト用に
設定し、フック全体のワークフローを通しで確認する。

## ベストプラクティス

1. **フックを独立に保つ**: 実行順序に依存しない
2. **タイムアウトを使う**: 種別ごとに適切な上限を設定する
3. **エラーを丁寧に処理する**: 明確なエラーメッセージを出す
4. **複雑さを文書化する**: 発展パターンは README で説明する
5. **徹底的にテストする**: エッジケースと失敗モードをカバーする
6. **性能を監視する**: フックの実行時間を追跡する
7. **設定をバージョン管理する**
8. **逃げ道を用意する**: 必要時にフックを迂回できるようにする

## よくある落とし穴

```bash
# ❌ フックの実行順序を仮定する
# （同一イベント内のフックは並列実行される）

# ❌ 長時間実行のフック
sleep 120  # タイムアウトしてワークフローをブロックする

# ❌ 例外の未処理
cat "$file_path"  # ファイルがなければクラッシュする

# ✅ 適切なエラー処理
if [ ! -f "$file_path" ]; then
  echo '{"continue": true, "systemMessage": "ファイルが見つからないためチェックをスキップ"}' >&2
  exit 0
fi
```

## まとめ

発展的なフックパターンは、信頼性と性能を保ちつつ高度な自動化を可能にする。
基本フックで足りないときに使い、常にシンプルさと保守性を優先する。
