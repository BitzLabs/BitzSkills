# 3. SDK リファレンス (SDK Reference)

## 3.1 インストール方法
Claude の自律エージェントループを自作アプリケーションに組み込むための **Claude Agent SDK** は、TypeScript/Node.js および Python 環境向けに提供されています。

### TypeScript/Node.js
```bash
npm install @anthropic-ai/claude-agent-sdk
```

### Python
```bash
pip install claude-agent-sdk
```

## 3.2 認証設定 (Authentication)
SDK の実行には、認証情報（API キー）が必須です。基本的には環境変数から読み込まれます。

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

また、Bedrock または Vertex AI 経由で Claude を利用する場合は、以下の環境変数を設定して統合します。
- **Bedrock の場合**:
  ```bash
  export CLAUDE_CODE_USE_BEDROCK=1
  export AWS_ACCESS_KEY_ID="your-access-key"
  export AWS_SECRET_ACCESS_KEY="your-secret-key"
  export AWS_DEFAULT_REGION="us-east-1"
  ```
- **Vertex AI の場合**:
  ```bash
  export CLAUDE_CODE_USE_VERTEX=1
  export CLOUD_SDK_PROJECT="your-gcp-project-id"
  export GOOGLE_APPLICATION_CREDENTIALS="/path/to/key.json"
  ```

## 3.3 主要 API とオプション
SDK の最も中心的なインターフェースは、自律ツール実行ループを制御する `query` 関数です。

### `query(prompt, options)` の基本オプション:
- **`prompt`** (必須): エージェントに与える指示テキスト。
- **`model`** (任意): 使用するモデル。省略した場合は `claude-3-5-sonnet-latest` が使用されます。
- **`maxSteps`** (任意): エージェントが 1 回のクエリで自律的に繰り返すツールの最大ステップ数（デフォルトは 30 前後）。
- **`allowedTools`** (任意): 実行を許可するツールのリスト。
- **`mcpServers`** (任意): 接続する MCP サーバーのリストとその引数。

## 3.4 基本コード例
### TypeScript の例
```typescript
import { query } from '@anthropic-ai/claude-agent-sdk';

async function run() {
  const prompt = "src/utils.ts に含まれる不正な例外処理を修正してテストをパスさせてください。";
  
  try {
    // query は非同期イテレータを返し、エージェントからの途中メッセージを逐次取得できる
    const stream = await query(prompt, {
      model: "claude-3-5-sonnet-latest",
      maxSteps: 15
    });

    for await (const chunk of stream) {
      if (chunk.type === 'message') {
        console.log(`[Claude]: ${chunk.content}`);
      } else if (chunk.type === 'tool_use') {
        console.log(`[Tool Use]: Running ${chunk.toolName} with args:`, chunk.args);
      } else if (chunk.type === 'tool_result') {
        console.log(`[Tool Result]: ${chunk.status}`);
      }
    }
    console.log("エージェントの処理が完了しました。");
  } catch (error) {
    console.error("エラーが発生しました:", error);
  }
}

run();
```

### Python の例
```python
import asyncio
from claude_agent_sdk import query

async def main():
    prompt = "auth.py のバグを特定し、修正してください。"
    
    # Python の非同期ジェネレータを用いた実装
    async for event in query(prompt=prompt, max_steps=20):
        if event.type == "message":
            print(f"[Claude]: {event.content}")
        elif event.type == "tool_use":
            print(f"[Tool Call]: {event.tool_name} (Args: {event.args})")
        elif event.type == "tool_result":
            print(f"[Tool Result]: {event.status}")

if __name__ == "__main__":
    asyncio.run(main())
```

## 3.5 CI/CD および外部システムとの統合方法
### 1. GitHub Actions による自動 PR レビュー
プルリクエストが作成された際に、Claude Code を使って自動的にコードレビューを行い、PR 内に直接コメントを投稿するワークフローの構築例です。

```yaml
name: Claude Code PR Reviewer

on:
  pull_request:
    types: [opened, synchronize]

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Install Claude Code CLI
        run: npm install -g @anthropic-ai/claude-code

      - name: Run Review Task
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          # Git の変更差分を取得
          git diff origin/${{ github.base_ref }}...HEAD > pr_diff.patch
          
          # Claude Code に差分を流し込んでレビューさせ、その結果をマークダウンとして取得
          claude -p "添付のパッチファイル pr_diff.patch を分析し、バグの懸念、スタイル違反、セキュリティ脆弱性があれば指摘してください。指摘は GitHub コメント用にマークダウン形式で簡潔に出力してください。" > review_result.md
          
          # GitHub API を使って PR にコメントを投稿
          gh pr comment ${{ github.event.number }} --body-file=review_result.md
```

### 2. 監視システム（アラート）との統合
プロダクション環境でのエラーログや Sentry の警告を検知した際、SDK を介して障害原因の調査からパッチの自動生成までを自律的に開始させることができます。
```python
# 疑似コード: アラートフックによる自動修復エージェント
def on_sentry_alert(issue_id, error_message, file_path):
    prompt = f"Sentry アラートが発生しました。エラー: {error_message}。対象ファイル: {file_path}。原因を調査し、バグ修正のプルリクエストを作成してください。"
    # SDK を呼び出してバックグラウンドで解決させる
    asyncio.run(run_auto_healer_agent(prompt))
```
