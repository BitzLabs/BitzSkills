# 3. SDK リファレンス (SDK Reference)

## 3.1 概要
**Antigravity SDK** は、自律型AIエージェントの構築、テスト、実行をプログラムから制御するための開発者向け SDK です。現在、**Python** 環境向けのパッケージである `google-antigravity` が提供されており、CLI や Desktop IDE と同様の「Antigravity Runtime」の上で動作します。

これにより、プログラムが実行するすべてのツール呼び出し（ファイルの読み書き、コマンド実行など）が共通のセキュリティ・サンドボックスやポリシー、状態管理エンジンによって安全に処理されます。

## 3.2 インストール方法
SDK は PyPI に公開されており、標準のパッケージマネージャでインストールします。

```bash
pip install google-antigravity
```

> [!IMPORTANT]
> SDK はコンパイル済みの Antigravity 2.0 ランタイムバイナリを含んでいるため、ソースコードを直接クローンするのではなく、必ず `pip` 等のパッケージインストーラーを介して正規に導入してください。

---

## 3.3 認証設定と接続モード
SDK は実行環境に合わせて以下の3つの主要な認証方式をサポートしています。

### 1. Application Default Credentials (ADC) - 推奨
本番環境や Google Cloud 上での利用、または開発者のローカル環境で GCP のリソースにアクセスする際の標準的な方法です。
事前に gcloud CLI を使って認証を完了させておくと、SDK が環境変数を検知して自動的に認証を行います。

```bash
gcloud auth application-default login
```

### 2. Vertex AI (Gemini Enterprise) 統合
企業向けプラットフォームである Vertex AI (Gemini Enterprise Agent Platform) をバックエンドとして利用する場合の設定です。`LocalAgentConfig` に対し、`vertex=True`、接続するプロジェクトID、ロケーションを指定します。

```python
from google.antigravity import Agent, LocalAgentConfig

config = LocalAgentConfig(
    vertex=True,
    project="your-gcp-project-id",  # 対象のGCPプロジェクトID
    location="us-central1"           # 対象のリージョン
)
```

### 3. API キー認証 (開発用・簡易設定)
GCP リソースへの接続が不要な軽量なテストや、外部の API ゲートウェイを経由する場合には、直接 API キーをコンフィグに渡すことができます。

```python
config = LocalAgentConfig(
    api_key="AIzaSy...",
    system_instructions="You are a specialized code generation agent."
)
```

---

## 3.4 基本実装コード例

以下は、Python の `asyncio` を利用して非同期にエージェントセッションを立ち上げ、チャットを行う基本的なコード例です。

```python
import asyncio
from google.antigravity import Agent, LocalAgentConfig

async def run_agent():
    # エージェント設定の初期化
    config = LocalAgentConfig(
        system_instructions="あなたはプロジェクトの依存関係をチェックし、脆弱性を探すセキュリティアナリストです。"
    )
    
    # エージェントインスタンスの生成とライフサイクル管理
    # コンテキストマネージャ (async with) により、接続とセッションの後処理を自動化
    async with Agent(config) as agent:
        print("--- エージェントセッションを開始します ---")
        
        # 最初の指示の送信
        response = await agent.chat("現在のワークスペース内の package.json に古い依存関係がないか確認してください。")
        print("\n[エージェント応答]:")
        print(await response.text())
        
        # 継続チャット（コンテキストが維持されます）
        follow_up = await agent.chat("発見したリスクに対する推奨のアップデートコマンドを提示してください。")
        print("\n[エージェント応答 (追記)]:")
        print(await follow_up.text())

if __name__ == "__main__":
    # 非同期イベントループでの実行
    asyncio.run(run_agent())
```

---

## 3.5 外部システムおよび CI/CD との統合方法

### 1. 自動コードレビューとビルド検証パイプライン
SDK を利用することで、GitHub Actions や GitLab CI などの CI/CD パイプライン内で「コミットされた差分コードに対する自動レビュー」や「品質検査」を自動化するスクリプトを記述できます。

```python
# CI環境でプルリクエストの差分ファイルを検証する例
import os
import sys
import asyncio
from google.antigravity import Agent, LocalAgentConfig

async def ci_review():
    config = LocalAgentConfig(
        # 安全のためにCI環境では自動進行させず、許可制にする設定等も可能
        sandbox=True
    )
    async with Agent(config) as agent:
        diff_file = os.environ.get("GITHUB_SHA") # 例
        prompt = f"コミット {diff_file} で発生したコード変更について、セキュリティとスタイルの両面からレビューを実施し、問題があればレポートしてください。"
        
        response = await agent.chat(prompt)
        report = await response.text()
        print(report)
        
        if "CRITICAL ERROR" in report or "SECURITY VULNERABILITY" in report:
            print("CI REVIEW FAILED: 重大な問題が検出されました。")
            sys.exit(1) # ビルド失敗として終了
            
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(ci_review())
```

### 2. 状態（セッション）のシリアライズと再開
SDK では、実行中のエージェントセッションの状態（チャット履歴や実行済みのツール結果など）を永続化（シリアライズ）し、別のプロセスでデシリアライズして途中から処理を再開する仕組みが提供されています。これにより、長時間に及ぶ自動コーディングタスクや人間による確認ステップを挟む非同期ワークフローを構築可能です。
