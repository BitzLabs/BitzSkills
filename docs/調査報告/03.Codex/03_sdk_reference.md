# 3. SDK リファレンス (SDK Reference)

OpenAI Codex は、プログラムから直接エージェントの動作を制御するための SDK を提供しています。これにより、独自の開発ツール、社内ポータル、あるいは CI/CD パイプラインへのエージェント機能の統合が可能です。

---

## 3.1 対応言語とインストール方法

公式には **TypeScript (Node.js)** および **Python** の2つの環境用のライブラリが提供されています。

### TypeScript / Node.js
* **要件**: Node.js 18 以上
* **パッケージ名**: `@openai/codex-sdk`
* **インストール**:
  ```bash
  npm install @openai/codex-sdk
  ```

### Python
* **要件**: Python 3.10 以上
* **パッケージ名**: `openai-codex`
* **インストール**:
  ```bash
  pip install openai-codex
  ```

---

## 3.2 認証設定

SDK を使用するプログラムを認証するには、主に2つの方法があります。

1. **環境変数による設定（推奨）**
   - ローカルログインセッションを利用する場合: `CODEX_HOME` 環境変数を設定し、CLIで `codex login` して得られた `auth.json` を共有します。
   - APIキーによるスタンドアロン実行: `OPENAI_API_KEY` 環境変数に有効なAPIキーを設定します。
2. **コード内での設定**
   - SDK インスタンス化の際にコンストラクタパラメータとして直接渡します。

---

## 3.3 TypeScript SDK 基本コード例

TypeScript SDK は、エージェントを動かす「スレッド（Thread）」と、各会話のターン（Turn）を抽象化したシンプルな API を提供します。

```typescript
import { Codex } from "@openai/codex-sdk";

async function main() {
  // 1. クライアントの初期化 (APIキーを直接指定することも可能)
  const codex = new Codex({
    apiKey: process.env.OPENAI_API_KEY, // 省略した場合は環境変数を自動参照
    // workingDirectory: "./target-project" // 制御対象のプロジェクトルート
  });

  // 2. 新しいスレッドの開始
  const thread = codex.startThread({
    // 初期設定やサンドボックスモードの上書きが可能
    sandboxMode: "workspace-write"
  });
  console.log(`Started Thread ID: ${thread.id}`);

  // 3. タスクの実行 (非同期 Promise)
  console.log("Running diagnosis task...");
  const turn = await thread.run("Check if the repository compiles correctly and fix if there are any obvious typescript compilation errors.");

  // 結果の出力
  console.log("--- Task Completed ---");
  console.log(`Status: ${turn.status}`); // 'success', 'failure', 'aborted'
  console.log(`Summary: ${turn.summary}`);
  
  if (turn.diffs && turn.diffs.length > 0) {
    console.log("Proposed Changes (Diffs):");
    turn.diffs.forEach(diff => {
      console.log(`File: ${diff.filePath}`);
      console.log(diff.patch);
    });
  }

  // 4. 同じスレッドで会話を継続
  const nextTurn = await thread.run("Run the tests now to verify the fixes.");
  console.log(`Test Result: ${nextTurn.summary}`);
}

main().catch(console.error);
```

### ストリーミング実行例 (`runStreamed`)
エージェントの思考やログ出力をリアルタイムにコンソールに出力する場合は、ストリーミング用の API を使用します。

```typescript
import { Codex } from "@openai/codex-sdk";

async function runStreaming() {
  const codex = new Codex();
  const thread = codex.startThread();

  const stream = thread.runStreamed("Refactor index.ts to use async/await.");

  // イベント駆動でエージェントのアクティビティを監視
  stream.on("delta", (chunk) => {
    // エージェントのチャットメッセージの差分を出力
    process.stdout.write(chunk.content);
  });

  stream.on("tool_started", (tool) => {
    console.log(`\n[Tool Executing] ${tool.name} with inputs:`, tool.input);
  });

  stream.on("tool_completed", (tool) => {
    console.log(`\n[Tool Finished] ${tool.name} (Exit code: ${tool.exitCode})`);
  });

  const finalTurn = await stream.finalResult();
  console.log(`\nStream ended. Status: ${finalTurn.status}`);
}
```

---

## 3.4 Python SDK 基本コード例

Python SDK も TypeScript SDK と同様のオブジェクト指向設計を踏襲しています。サンドボックスモードは文字列ではなく `Sandbox` 列挙型で明示的に指定し、スレッド開始は `thread_start(...)`、ターン結果は `result.final_response` で取得します。`Sandbox.workspace_write` のように列挙値を渡すことで、実行権限の範囲を明確に表現できます。

```python
import os
from openai_codex import Codex, Sandbox

def main():
    # クライアント初期化
    codex = Codex(api_key=os.getenv("OPENAI_API_KEY"))

    # スレッド開始（サンドボックスは Sandbox 列挙型で指定）
    thread = codex.thread_start(sandbox=Sandbox.workspace_write)
    print(f"Thread started: {thread.id}")

    # ターンの実行
    result = thread.run("List all TODOs in the source files.")

    # 最終応答の確認
    print("Agent Final Response:")
    print(result.final_response)

if __name__ == "__main__":
    main()
```

> [!NOTE]
> 非同期処理が必要な場合は `AsyncCodex` クラスを使用します（`await codex.thread_start(...)` / `await thread.run(...)`）。旧 API の `codex.start_thread()` や `turn.summary` / `turn.diffs` は現行では上記に置き換わっています。

---

## 3.5 双方向 JSON-RPC プロトコル (`codex-app-server`)

SDK の内部では、ローカルで起動された `codex-app-server` プロセスに対して **JSON-RPC 2.0 (via stdio / WebSocket)** を用いて要求を送信しています。
SDK を介さず、低レベルでこのプロトコルを叩くことで、よりリッチな統合（セッションの高度な管理、スレッドの分岐など）を実現できます。

### 主要な JSON-RPC メソッド

| メソッド | 説明 |
| :--- | :--- |
| `thread/list` | 過去に保存されたすべてのスレッドのリスト（ID、タイトル、タイムスタンプ）をフィルタ付きで取得します。 |
| `thread/read` | 特定のスレッドIDの全メッセージ履歴とターン履歴を、再開せずに「読み取り専用」で取得します。 |
| `thread/fork` | 既存のスレッドの特定時点から新しくスレッドを分岐（フォーク）させ、別の実行ラインを試します。 |
| `tool/approve` | クライアントからサーバーに対し、一時停止しているツールの実行を承認します（双方向フロー）。 |

### イベントストリーム通知（サーバーからクライアント）
* `item/started`: ターン内の特定のステップ（思考、ツール実行など）が開始された。
* `item/completed`: ステップが正常に完了した。
* `item/agentMessage/delta`: チャットテキストの差分（ストリーミングデータ）。

---

## 3.6 CI/CD や外部システムとの統合方法

### CI パイプラインでの自動バグ修正
GitHub Actions 等の CI ランナー上でテストが失敗した際、Codex SDK を用いて自動でコード修正の PR を作成するワークフロー例です。

```typescript
import { Codex } from "@openai/codex-sdk";
import { execSync } from "child_process";

async function runAutoFix() {
  const codex = new Codex();
  const thread = codex.startThread({ sandboxMode: "workspace-write" });
  
  // テストエラーログを読み込む
  const testLogs = execSync("npm test").toString();
  
  const turn = await thread.run(
    `The test suite failed with the following errors. Please diagnose the source code and modify it to pass the tests. Keep modifications minimal.\n\nErrors:\n${testLogs}`
  );
  
  if (turn.status === "success" && turn.diffs && turn.diffs.length > 0) {
    // 差分が生成された場合、Gitブランチを切ってコミットし、PRを出す
    execSync("git checkout -b codex-autofix");
    // ファイル変更はエージェントによって適用済み
    execSync("git add .");
    execSync("git commit -m 'chore: auto-fix CI test failures via Codex'");
    execSync("git push origin codex-autofix");
    console.log("Pushed auto-fix branch successfully.");
  } else {
    console.log("No fix could be determined or applied.");
  }
}

runAutoFix();
```
> [!IMPORTANT]
> CI/CD などの無人環境で実行する場合、ツール実行のたびに承認待ちでプロセスがハングするのを防ぐため、SDKパラメータで `sandboxMode: "workspace-write"` や `dangerouslyBypassApprovals: true` を明示的に指定する必要があります。
