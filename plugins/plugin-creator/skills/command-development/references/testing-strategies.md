# コマンドのテスト戦略

スラッシュコマンドを配布前に体系的にテストするための戦略。

## 概要

テストにより、コマンドが正しく動作し、エッジケースを処理し、良いユーザー
体験を提供することを保証する。体系的なテストは問題を早期に発見する。

## テストレベル

### Level 1: 構文と構造の検証

**検証項目**: YAML frontmatter の構文、マークダウン形式、配置とファイル名。

```bash
# frontmatterの閉じマーカー確認（2つあるべき）
head -n 20 .claude/commands/my-command.md | grep -c "^---"

# 拡張子と配置の確認
test -f .claude/commands/my-command.md && echo "Found" || echo "Missing"
```

自動検証スクリプトの例:

```bash
#!/bin/bash
# validate-command.sh — コマンドファイルの構造を検証する

COMMAND_FILE="$1"

if [ ! -f "$COMMAND_FILE" ]; then
  echo "エラー: ファイルが見つかりません: $COMMAND_FILE"
  exit 1
fi

if [[ ! "$COMMAND_FILE" =~ \.md$ ]]; then
  echo "エラー: 拡張子は .md である必要があります"
  exit 1
fi

# frontmatter があれば構文を検証
if head -n 1 "$COMMAND_FILE" | grep -q "^---"; then
  MARKERS=$(head -n 50 "$COMMAND_FILE" | grep -c "^---")
  if [ "$MARKERS" -ne 2 ]; then
    echo "エラー: frontmatter が不正（'---' はちょうど2つ必要）"
    exit 1
  fi
  echo "✓ frontmatter の構文は正常"
fi

if [ ! -s "$COMMAND_FILE" ]; then
  echo "エラー: ファイルが空です"
  exit 1
fi

echo "✓ コマンドファイルの構造は正常"
```

### Level 2: frontmatter フィールドの検証

**検証項目**: フィールドの型、値の妥当性（model が sonnet/opus/haiku か、
description の長さなど）。

```bash
#!/bin/bash
# validate-frontmatter.sh — frontmatterフィールドを検証する

COMMAND_FILE="$1"
FRONTMATTER=$(sed -n '/^---$/,/^---$/p' "$COMMAND_FILE" | sed '1d;$d')

[ -z "$FRONTMATTER" ] && { echo "frontmatterなし"; exit 0; }

if echo "$FRONTMATTER" | grep -q "^model:"; then
  MODEL=$(echo "$FRONTMATTER" | grep "^model:" | cut -d: -f2 | tr -d ' ')
  if ! echo "sonnet opus haiku" | grep -qw "$MODEL"; then
    echo "エラー: 無効なmodel '$MODEL'（sonnet / opus / haiku のみ）"
    exit 1
  fi
fi

if echo "$FRONTMATTER" | grep -q "^description:"; then
  DESC=$(echo "$FRONTMATTER" | grep "^description:" | cut -d: -f2-)
  [ "${#DESC}" -gt 80 ] && echo "警告: description が ${#DESC} 文字（60文字以内推奨）"
fi

echo "✓ frontmatter フィールドは正常"
```

### Level 3: 手動での呼び出しテスト

```bash
# 1. デバッグモードで起動
claude --debug

# 2. /help にコマンドが出るか確認
# 3. 引数なしで実行 → 妥当なエラーか挙動を確認
# 4. 有効な引数で実行 → 期待どおりか確認
# 5. デバッグログを確認
```

### Level 4: 引数のテスト

| ケース | コマンド | 期待結果 |
| --- | --- | --- |
| 引数なし | `/cmd` | 丁寧なエラーまたは使い方の提示 |
| 1引数 | `/cmd arg1` | $1 が正しく展開される |
| 2引数 | `/cmd arg1 arg2` | $1 と $2 が展開される |
| 余分な引数 | `/cmd a b c d` | 全部取得されるか、余りが適切に無視される |
| 空白を含む | `/cmd "arg with spaces"` | クォートが正しく処理される |
| 空文字 | `/cmd ""` | 空文字列として処理される |

### Level 5: ファイル参照のテスト

```bash
# テストファイルを作成して単一参照・複数参照を確認
echo "Test content" > /tmp/test-file.txt
> /my-command /tmp/test-file.txt

# 存在しないファイル → 丁寧なエラー処理を確認
> /my-command /tmp/nonexistent.txt

# 大きいファイル → 妥当な挙動（切り詰め・警告）を確認
```

### Level 6: bash実行のテスト

```bash
# テスト用コマンドを作成
cat > .claude/commands/test-bash.md << 'EOF'
---
description: bash実行のテスト
allowed-tools: Bash(echo:*), Bash(date:*)
---

現在時刻: !`date`
テスト出力: !`echo "Hello from bash"`

上記出力を分析する...
EOF

# /test-bash を実行し、出力の展開とエラーの有無を確認する

# 許可されていないコマンドが拒否されることも確認する
# （allowed-tools: Bash(echo:*) のコマンドで !`ls -la /` → 拒否されるべき）
```

### Level 7: 統合テスト

- **コマンド + フック**: コマンド実行時にフックが発火して検証するか
- **コマンド連鎖**: `/workflow-init` → 状態ファイル作成 →
  `/workflow-step2` → 状態を読んで実行 → `/workflow-complete` → 掃除
- **コマンド + MCP**: MCPサーバーが起動し、ツール呼び出しが成功するか

## 自動テスト

### テストスイート

```bash
#!/bin/bash
# test-commands.sh — 全コマンドの一括検証

TEST_DIR=".claude/commands"
FAILED=0

for cmd_file in "$TEST_DIR"/*.md; do
  echo "テスト中: $(basename "$cmd_file" .md)"
  ./validate-command.sh "$cmd_file" || ((FAILED++))
  ./validate-frontmatter.sh "$cmd_file" || ((FAILED++))
done

echo "失敗: $FAILED"
exit $FAILED
```

### pre-commit フック

コミット時に変更されたコマンドだけ検証する:

```bash
#!/bin/bash
COMMANDS_CHANGED=$(git diff --cached --name-only | grep "\.claude/commands/.*\.md")
[ -z "$COMMANDS_CHANGED" ] && exit 0

for cmd in $COMMANDS_CHANGED; do
  ./scripts/validate-command.sh "$cmd" || exit 1
done
```

### CI/CD

```yaml
# .github/workflows/test-commands.yml
name: Test Commands
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: コマンド構造の検証
        run: |
          for cmd in .claude/commands/*.md; do
            ./scripts/validate-command.sh "$cmd"
          done
```

## エッジケーステスト

```bash
# 空引数
> /cmd ""

# 特殊文字
> /cmd "arg with spaces"
> /cmd arg/with/slashes
> /cmd 'arg with "quotes"'

# 非常に長い引数
> /cmd $(python -c "print('a' * 10000)")

# 失敗するbashコマンド
!`exit 1`
!`command-that-does-not-exist`
```

## パフォーマンス・UXテスト

**応答時間**: 数回実行して平均と分散を見る（軽量コマンドは3秒未満が目安）。

**ユーザビリティチェックリスト:**

- [ ] コマンド名が直感的
- [ ] `/help` の説明が明確
- [ ] 引数が文書化されている
- [ ] エラーメッセージが役立つ
- [ ] 出力が読みやすい
- [ ] 長時間かかる処理は進捗を示す
- [ ] 結果が次のアクションにつながる

## リリース前チェックリスト

**構造**: 配置・拡張子・frontmatter構文・マークダウン構文
**機能**: `/help` 表示・エラーなし実行・引数・ファイル参照・bash実行
**エッジケース**: 引数欠落・無効引数・存在しないファイル・特殊文字・長い入力
**統合**: 他コマンド・フック・MCP・状態管理との連携
**品質**: 性能・セキュリティ・エラーメッセージ・出力整形・ドキュメント

## テスト失敗時のデバッグ

**`/help` に出ない**: 配置とパーミッションを確認し、frontmatter 構文を見て、
Claude Code を再起動する。

**引数が展開されない**: `$1` / `$ARGUMENTS` の構文を確認し、
まず最小のテストコマンドで動作を切り分ける。

**bashが実行されない**: `allowed-tools` に該当の Bash パターンがあるか、
バッククォート構文が正しいか、コマンド単体がターミナルで動くかを確認する。

**ファイル参照が働かない**: `@` 構文・ファイルの存在・パーミッションを確認する。

## ベストプラクティス

1. **早めに・頻繁にテスト**: 開発しながら検証する
2. **検証を自動化**: スクリプトで再現可能なチェックにする
3. **ハッピーパス以外も**: エッジケースを必ずテストする
4. **他人に試してもらう**: 公開前にフィードバックを得る
5. **テストシナリオを残す**: リグレッションテストに使う
