# 発展プラグインの例

MCP統合・共有ライブラリ・多段構成を備えたエンタープライズ級プラグイン。

## ディレクトリ構造

```
enterprise-devops/
├── .claude-plugin/
│   └── plugin.json
├── commands/
│   ├── ci/            (build.md, test.md, deploy.md)
│   ├── monitoring/    (status.md, logs.md)
│   └── admin/         (configure.md, manage.md)
├── agents/
│   ├── orchestration/ (deployment-orchestrator.md, rollback-manager.md)
│   └── specialized/   (kubernetes-expert.md, terraform-expert.md, security-auditor.md)
├── skills/
│   ├── kubernetes-ops/
│   │   ├── SKILL.md
│   │   ├── references/  (deployment-patterns.md, troubleshooting.md, security.md)
│   │   ├── examples/    (basic-deployment.yaml, stateful-set.yaml, ingress-config.yaml)
│   │   └── scripts/     (validate-manifest.sh, health-check.sh)
│   ├── terraform-iac/
│   │   ├── SKILL.md
│   │   ├── references/best-practices.md
│   │   └── examples/module-template/
│   └── ci-cd-pipelines/
│       ├── SKILL.md
│       └── references/pipeline-patterns.md
├── hooks/
│   ├── hooks.json
│   └── scripts/
│       ├── security/   (scan-secrets.sh, validate-permissions.sh, audit-changes.sh)
│       ├── quality/    (check-config.sh, verify-tests.sh)
│       └── workflow/   (notify-team.sh, update-status.sh)
├── .mcp.json
├── servers/
│   ├── kubernetes-mcp/     (index.js, package.json, lib/)
│   ├── terraform-mcp/      (main.py, requirements.txt)
│   └── github-actions-mcp/ (server.js, package.json)
├── lib/
│   ├── core/          (logger.js, config.js, auth.js)
│   ├── integrations/  (slack.js, pagerduty.js, datadog.js)
│   └── utils/         (retry.js, validation.js)
└── config/
    ├── environments/  (production.json, staging.json, development.json)
    └── templates/     (deployment.yaml, service.yaml)
```

## マニフェスト

コマンド・エージェントがネストしているため、カスタムパスの列挙が必須になる:

```json
{
  "name": "enterprise-devops",
  "version": "2.3.1",
  "description": "エンタープライズCI/CDパイプライン・インフラ管理・監視の包括的なDevOps自動化",
  "author": {
    "name": "DevOps Platform Team",
    "email": "devops-platform@company.com",
    "url": "https://company.com/teams/devops"
  },
  "homepage": "https://docs.company.com/plugins/devops",
  "repository": { "type": "git", "url": "https://github.com/company/devops-plugin.git" },
  "license": "Apache-2.0",
  "keywords": ["devops", "ci-cd", "kubernetes", "terraform", "monitoring"],
  "commands": [
    "./commands/ci",
    "./commands/monitoring",
    "./commands/admin"
  ],
  "agents": [
    "./agents/orchestration",
    "./agents/specialized"
  ],
  "hooks": "./hooks/hooks.json",
  "mcpServers": "./.mcp.json"
}
```

## MCPサーバー定義（.mcp.json）

プラグインに同梱した自前サーバーを `${CLAUDE_PLUGIN_ROOT}` 経由で起動する:

```json
{
  "mcpServers": {
    "kubernetes": {
      "command": "node",
      "args": ["${CLAUDE_PLUGIN_ROOT}/servers/kubernetes-mcp/index.js"],
      "env": {
        "KUBECONFIG": "${KUBECONFIG}",
        "LOG_LEVEL": "info"
      }
    },
    "terraform": {
      "command": "python",
      "args": ["${CLAUDE_PLUGIN_ROOT}/servers/terraform-mcp/main.py"],
      "env": {
        "TF_WORKSPACE": "${TF_WORKSPACE:-default}"
      }
    },
    "github-actions": {
      "command": "node",
      "args": ["${CLAUDE_PLUGIN_ROOT}/servers/github-actions-mcp/server.js"],
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}"
      }
    }
  }
}
```

## 設計上のポイント

### 共有ライブラリ（lib/）

コマンド・フック・MCPサーバーが同じロジック（ログ・認証・リトライ）を
`lib/` から共有する。重複を排除し、挙動を一貫させる。

```bash
#!/bin/bash
source "${CLAUDE_PLUGIN_ROOT}/lib/core/logger.sh"
log_info "デプロイを開始します"
```

### 環境別設定（config/environments/）

production / staging / development の設定を分離し、コマンドが実行時に
適切なファイルを選択する。認証情報は設定ファイルに書かず環境変数で渡す。

### セキュリティ自動化（hooks/scripts/security/）

- `scan-secrets.sh`: コミット前に認証情報の混入をスキャン
- `validate-permissions.sh`: インフラ変更の権限チェック
- `audit-changes.sh`: 変更の監査ログ記録

### 監視連携（lib/integrations/）

Slack への通知、PagerDuty のアラート、Datadog へのメトリクス送信を
共有ライブラリとして実装し、フック・コマンドの両方から使う。

## ポイント

1. **多段構成**: コンポーネントをカテゴリ別サブフォルダで整理し、
   マニフェストのカスタムパスで列挙する
2. **MCPサーバー同梱**: 自前サーバーを `servers/` に置き
   `${CLAUDE_PLUGIN_ROOT}` で起動する
3. **共有ライブラリ**: 横断的関心事（ログ・認証・通知）を `lib/` に集約する
4. **設定の外部化**: 環境別設定と認証情報の分離
5. **セキュリティ第一**: フックによる自動検査を多層で組み込む

## このパターンが向く場面

- 大規模チーム・エンタープライズでの利用
- 複数の外部サービス統合が必要なプラグイン
- セキュリティ・監査要件があるワークフロー
- 100ファイルを超える規模のプラグイン

小さく始めたい場合は `minimal-plugin.md` / `standard-plugin.md` を先に参照。
