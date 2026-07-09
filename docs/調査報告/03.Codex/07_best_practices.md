# 7. ベストプラクティス (Best Practices)

OpenAI Codex を安全かつ効率的に運用するための実務指針を、公式ドキュメントの推奨に沿ってまとめます。設定キー・値は第6章で訂正した最新仕様に基づきます。

---

## 7.1 承認モードとサンドボックスの選び方

ローカル作業の低摩擦な既定は `sandbox_mode = "workspace-write"` ＋ `approval_policy = "on-request"`（CLI なら `--sandbox workspace-write --ask-for-approval on-request`）です。フルアクセスが必要な場合のみ `sandbox_mode = "danger-full-access"` ＋ `approval_policy = "never"` を明示的に選びます。

書き込み対象ディレクトリを追加したいだけなら、`danger-full-access` に広げるのではなく **`--add-dir` で書き込みルートを追加**する方が安全です（公式推奨）。

---

## 7.2 `--yolo`（`--dangerously-bypass-approvals-and-sandbox`）の運用

公式ドキュメント自身が "Only use inside an externally hardened environment" と明記しています。ローカル開発機での常用は非推奨です。CI/CD でも、専用の使い捨てランナー／コンテナ内でのみ使用してください。

---

## 7.3 AGENTS.md 設計

グローバル（`~/.codex/AGENTS.md`）に組織共通の作業合意を、リポジトリルートに基本ルールを、サブディレクトリ（例 `services/payments/AGENTS.override.md`）にチーム固有ルールを配置する階層設計が公式推奨パターンです。32KiB 上限に注意し、超える場合はディレクトリ単位で分割します。

---

## 7.4 承認疲れ対策と Auto-review

`approval_policy = { granular = { sandbox_approval = ..., rules = ..., mcp_elicitations = ..., request_permissions = ..., skill_approval = ... } }` で、プロンプトカテゴリ単位に自動許可／自動拒否を選別できます。すべてを `never` にする前に、まず granular で必要な箇所だけ人間確認を残す設計を検討します。

大量の承認要求が発生する自動化ワークフローでは `approvals_reviewer = "auto_review"` を使い、レビュアー・サブエージェントに一次判定させることで、人間の介入頻度を下げつつ「無条件 bypass（`--yolo`）」より安全な運用ができます。

---

## 7.5 サブエージェントの使い方

Codex はサブエージェントを自動発火しない仕様です（第6.3節）。そのため、プロンプトで **明示的に**「並列サブエージェントで実施」「役割分担」「待ち合わせの有無」「返してほしい要約の形式」を指定します。書き込み系の並列化は競合が起きやすいため、読み取り・調査・テスト実行系から適用します。

---

## 7.6 MCP 運用

`mcp_servers.<id>.required = true` で必須サーバの起動失敗時にセッション開始／再開自体を失敗させ、サイレントな機能欠落を防げます。`enabled_tools` / `disabled_tools` でツール単位の許可リスト／拒否リストを設定し、攻撃面を絞ります。

---

## 7.7 CI/CD（`codex exec`）運用

`--full-auto` フラグは非推奨で、Codex が警告を出します。代わりに `--sandbox workspace-write`（必要なら `--ask-for-approval never`）を明示指定します。`codex exec resume --last` / `--all` でセッション再開が可能なため、失敗したジョブの再試行にはセッション ID を保存しておきます。認証は `codex login --with-api-key`（stdin 経由）を用い、`codex login status` の終了コードで自動化スクリプト内の認証確認ができます。

---

## 7.8 コスト最適化

モデル選定はタスク粒度で分けます。`gpt-5.5` は複雑な計画・多段推論に、`gpt-5.4-mini` は探索・大量ファイルの下読み・サブエージェントのワーカーに向きます。`model_reasoning_effort` を `low` / `medium` / `high` / `xhigh` で明示調整し、単純作業に高コストな `xhigh` を使わないようにします。

---

## 7.9 セキュリティ運用

`danger-full-access` はファイルシステム・ネットワーク境界の**両方**を完全に外す設定であり、`workspace-write`（ワークスペース内書き込み限定）との違いを運用者が明確に理解する必要があります。

Hooks は公式が「完全な強制境界ではなく有用なガードレール」と明記しています（モデルが迂回スクリプトを書いて Bash 経由で実行する可能性がある）。Hooks だけをセキュリティ境界として設計しないでください。

`@openai/codex` を騙る偽パッケージによる `auth.json`（認証トークン）窃取は、npm エコシステムのタイポスクワッティング全般に共通する現実的なリスクです。インストール前にパッケージ名・publisher を必ず確認します。
