# 第3章 SDK リファレンス (SDK Reference)

**Claude Agent SDK** は、Claude Code CLI を支えている自律型エージェントループ、コンテキスト管理、およびツール実行の仕組みを、Python や Node.js/TypeScript からプログラムとして呼び出すための SDK です。

> [!NOTE]
> 本 SDK は、生の LLM API を叩くための一般的な `anthropic` パッケージとは異なります。
> エージェントとしてファイルの操作や Bash の実行、計画立案を自動的に行うループをプログラムに内包させるためのものです。

---

## 3.1 インストール方法

### Node.js / TypeScript (Node.js 18+)

```bash
npm install @anthropic-ai/claude-agent-sdk
```

### Python (Python 3.10+)

```bash
pip install claude-agent-sdk
```

---

## 3.2 認証設定 (Authentication)

SDKを使用する際には、非インタラクティブ環境で実行されることが多いため、環境変数を通じた認証を行います。

### 標準的な API キーの利用

環境変数 `ANTHROPIC_API_KEY` に、Anthropic Console から発行した API キーを設定します。

- **Linux / macOS:**
  ```bash
  export ANTHROPIC_API_KEY="your-api-key-here"
  ```
- **Windows (PowerShell):**
  ```powershell
  $env:ANTHROPIC_API_KEY="your-api-key-here"
  ```

### クラウドプロバイダー経由の認証

APIキーの代わりに AWS や Google Cloud などのマネージドサービス経由でモデルを利用する場合は、以下の環境変数を設定します。

- **Amazon Bedrock 経由の利用:**
  ```bash
  export CLAUDE_CODE_USE_BEDROCK=1
  # AWS 認証情報（AWS_ACCESS_KEY_ID、AWS_SECRET_ACCESS_KEY、AWS_REGION 等）を設定
  ```
- **Google Cloud Vertex AI 経由の利用:**
  ```bash
  export CLAUDE_CODE_USE_VERTEX=1
  # Google Application Credentials (JSONファイルのパスなど) を設定
  ```
- **Anthropic Platform on AWS 経由の利用:**
  ```bash
  export CLAUDE_CODE_USE_ANTHROPIC_AWS=1
  export ANTHROPIC_AWS_WORKSPACE_ID="your-workspace-id"
  ```

---

## 3.3 主要 API とオプション

主要な API エントリポイントは `query()` 関数です。また、セッションの対話を継続して維持するために `ClaudeSDKClient`（または `ClaudeAgentSession`）を使用できます。

### `ClaudeAgentOptions` の主要プロパティ

エージェントの挙動をカスタマイズするためのオプション引数です。

| プロパティ (TypeScript) | プロパティ (Python) | 説明 | 例 |
| :--- | :--- | :--- | :--- |
| `systemPrompt` | `system_prompt` | エージェントの基本指示（ペルソナ） | `"You are a security auditor."` |
| `model` | `model` | 使用する Claude モデル | `"claude-3-5-sonnet"` |
| `maxTurns` | `max_turns` | ツール実行ループの最大往復回数 | `10` |
| `cwd` | `cwd` | エージェントの作業ディレクトリパス | `"/path/to/project"` |
| `cliPath` | `cli_path` | 使用する claude CLI のカスタムパス | `"/usr/local/bin/claude"` |
| `allowedTools` | `allowed_tools` | ユーザー承認なしに実行を自動許可するツール | `["Read", "Grep", "Bash"]` |
| `disallowedTools` | `disallowed_tools` | 使用を明示的に禁止するツール | `["Write"]` |
| `permissionMode` | `permission_mode` | ツール実行の許可モード（`default`/`acceptEdits`/`bypassPermissions`） | `"acceptEdits"` |
| `settingSources` | `setting_sources` | `CLAUDE.md` やカスタムスキルなど、プロジェクト設定の読込制御 | `["local", "project"]` |

---

## 3.4 基本コード例

### Node.js / TypeScript の実装例

非同期イテレータを使用し、エージェントから送信される出力をストリーミングで受け取るコード例です。

```typescript
import { query } from "@anthropic-ai/claude-agent-sdk";

async function runAgent() {
  try {
    const stream = query({
      prompt: "package.json を確認して、セキュリティ脆弱性のある古い依存パッケージを特定し、npm update を実行してください",
      options: {
        cwd: process.cwd(),
        permissionMode: "acceptEdits", // ファイル編集は自動承認
        allowedTools: ["Read", "Bash"], // ReadとBashの使用を許可
        maxTurns: 8,
      }
    });

    for await (const message of stream) {
      // メッセージのストリーミング出力を順次ターミナルへ表示
      process.stdout.write(message);
    }
  } catch (error) {
    console.error("Agent execution failed:", error);
  }
}

runAgent();
```

### Python の実装例

Python 3.10 以降で `asyncio` を使用した非同期ストリーミングの例です。

```python
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions

async def run_agent():
    options = ClaudeAgentOptions(
        cwd=".",
        permission_mode="acceptEdits",
        allowed_tools=["Read", "Bash"],
        max_turns=10
    )
    
    # queryは非同期ジェネレータを返すため、async for で受ける
    async for message in query(
        prompt="Find all Python files in the src/ directory and add docstrings to functions that lack them.",
        options=options
    ):
        print(message, end="", flush=True)

if __name__ == "__main__":
    asyncio.run(run_agent())
```

---

## 3.5 CI/CD および外部システムとの統合方法

自律エージェントを GitHub Actions などの CI/CD パイプラインやバッチジョブに統合する際のベストプラクティスです。

### 1. 非インタラクティブ（Headless）モードの徹底
パイプラインがユーザー入力を待ってフリーズしないように、必ず `permissionMode: "bypassPermissions"`（または CLI の `-p`）を指定します。
> [!IMPORTANT]
> 承認スキップを許可するには、設定で `allowDangerouslySkipPermissions` を `true` にするか、環境変数 `CLAUDE_ALLOW_DANGEROUSLY_SKIP_PERMISSIONS=1` を指定する必要があります。

### 2. 最小権限の原則 (Least Privilege)
CIのコンテキストでは、破壊的な操作を防ぐために `allowedTools` を `["Read", "Grep", "Glob"]`（読み取り専用）に制限するか、実行可能な Bash コマンドのスコープを `Bash(npm test)` や `Bash(git diff)` のように限定します。

### 3. OpenTelemetry を使った監視とコスト追跡
SDK は OpenTelemetry をサポートしています。長時間の自律ループによって発生するトークン消費量やエラー発生率を、Datadog や Honeycomb などの外部の監視バックエンドへ送信できます。

```bash
# OpenTelemetry エクスポートを有効にする環境変数例
export OTEL_EXPORTER_OTLP_ENDPOINT="https://otlp.telemetry.example.com"
export OTEL_SERVICE_NAME="claude-ci-agent"
```

### 4. べき等性（Idempotency）とブランチ保護
自律エージェントはバグの修正などで予期せぬ破壊的変更を行う可能性があります。CI上で動かす場合は、**直接 main ブランチに変更をコミットさせず**、専用のトピックブランチを作成させ、そこから Pull Request を作成するようなワークフローをエージェントに命令してください。
