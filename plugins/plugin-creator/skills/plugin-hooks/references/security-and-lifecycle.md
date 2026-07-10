# セキュリティ・パフォーマンス・ライフサイクル

## セキュリティのベストプラクティス

### 入力検証

```bash
#!/bin/bash
set -euo pipefail

input=$(cat)
tool_name=$(echo "$input" | jq -r '.tool_name')

# ツール名の形式を検証する
if [[ ! "$tool_name" =~ ^[a-zA-Z0-9_]+$ ]]; then
  echo '{"decision": "deny", "reason": "不正なツール名"}' >&2
  exit 2
fi
```

### パスの安全性

```bash
file_path=$(echo "$input" | jq -r '.tool_input.file_path')

# パストラバーサルを拒否する
if [[ "$file_path" == *".."* ]]; then
  echo '{"decision": "deny", "reason": "パストラバーサルを検出"}' >&2
  exit 2
fi

# 機微なファイルを拒否する
if [[ "$file_path" == *".env"* ]]; then
  echo '{"decision": "deny", "reason": "機微なファイル"}' >&2
  exit 2
fi
```

完全な例は `examples/validate-write.sh` / `examples/validate-bash.sh` を参照。

### その他

- **変数は必ずクォートする**: `echo "$file_path"`（インジェクション対策）
- **タイムアウトを設定する**: 既定はコマンド60秒 / プロンプト30秒
- **機密情報をログに出さない**

## パフォーマンス

一致するフックは**すべて並列実行**される。フック同士は互いの出力を
見られず、順序も非決定的なので、独立して動くよう設計する。
高速で決定的なチェックはコマンドフック、複雑な推論はプロンプトフックに
分担させる。

## 一時的に有効なフック

フラグファイルや設定で条件付きに動くフックを作れる:

```bash
#!/bin/bash
# フラグファイルがあるときだけ有効
FLAG_FILE="$CLAUDE_PROJECT_DIR/.enable-strict-validation"

if [ ! -f "$FLAG_FILE" ]; then
  exit 0  # フラグなし。検証をスキップ
fi

# フラグあり。検証を実行する
input=$(cat)
# ... 検証ロジック ...
```

有効化の仕組みをプラグインの README に必ず書くこと。

## ライフサイクルと制限

**フックはセッション開始時に読み込まれる。** 設定変更はホットスワップ
できず、Claude Code の再起動が必要:

1. hooks.json やスクリプトを編集する
2. Claude Code を終了して再起動する
3. `claude --debug` でテストする

起動時に検証が走る（不正な JSON は読み込み失敗、スクリプト欠落は警告）。
現在のセッションのフック一覧は `/hooks` コマンドで確認できる。

## デバッグ

```bash
# デバッグモードでフックの登録・実行ログ・入出力JSONを見る
claude --debug

# コマンドフックを単体テストする
echo '{"tool_name": "Write", "tool_input": {"file_path": "/test"}}' | \
  bash ${CLAUDE_PLUGIN_ROOT}/scripts/validate.sh
echo "Exit code: $?"

# JSON出力の妥当性を確認する
output=$(./your-hook.sh < test-input.json)
echo "$output" | jq .
```

