---
id: ADR-016
title: Agent Plugins準拠の複数プラグイン配布
status: accepted
relations:
  related:
    - ADR-009
---

# ADR-016 Agent Plugins準拠の複数プラグイン配布

## Context

Bitzを単一プラグインへ集約すると、EARS-AIの決定論的コア、SDD、品質、DDD、同期など、用途の異なる
機能が一括導入される。個人から数人のチームが必要な機能だけを選べるようにしつつ、CLIごとの独自形式へ
判定ロジックを複製しない配布境界が必要である。

Agent Plugins 1.0.0は、ルート`plugin.json`、`skills/`、`mcp.json`を用い、SkillsとMCP serversを
移植可能な構成要素として定義する。一方、標準の`plugin.json`にはプラグイン間依存の解決機構がなく、
配布、導入、権限、クライアント固有機能は各クライアントの管理範囲である。

## Decision

### 1. 配布単位

GitHubでホストする1つのBitzマーケットプレイスリポジトリから、複数の独立したAgent Plugins 1.0.0
準拠パッケージを提供する。各プラグインは自己完結したディレクトリとし、別プラグインのファイルを
相対パス、symlink、インストール先推測で参照しない。

```text
bitz-plugins/
├── .github/plugin/marketplace.json
├── .claude-plugin/marketplace.json
└── plugins/
    ├── bitz-core/
    ├── bitz-sdd/
    ├── bitz-quality/
    ├── bitz-ddd/
    └── bitz-sync/
```

マーケットプレイス形式はAgent Plugins本体仕様ではなくクライアント管理である。クライアント別カタログが
必要な場合も、単一のカタログ定義から生成して内容の一致をCIで検査する。

| 区分 | プラグイン | 責務 |
|---|---|---|
| 必須 | `bitz-core` | EARS-AI Parser、Semantic IR、Context Resolution、`check`、`verify`、`doctor`、共通Diagnostic、MCP境界 |
| 基本拡張 | `bitz-sdd` | IntentからDoneまでのSmall Flow、SDD Profile、タスク分解 |
| 将来拡張 | `bitz-quality` | 品質レビュー、テスト十分性、LLM advisory |
| 将来拡張 | `bitz-ddd` | DDD Profileとドメインモデリング支援 |
| 将来拡張 | `bitz-sync` | 仕様と実装の差分検出、改訂候補の提示 |

通常のAI-SDD利用には`bitz-core`と`bitz-sdd`を推奨するが、EARS-AI検査とCIだけを利用する場合は
`bitz-core`単独を許可する。将来の拡張も`bitz-core`だけへ依存し、拡張プラグイン間の必須依存を禁止する。

### 2. 標準境界

各パッケージはルート`plugin.json`で
`https://agent-plugins.org/schemas/1.0.0/plugin.schema.json`を宣言する。移植可能な機能は
`skills/`と`mcp.json`へ置き、agents、commands、hooksなどは必要な場合だけreverse-domain namespaceへ置く。
クライアント固有拡張がなくても、主要操作がSkillsとMCPで成立することを要求する。

`bitz-core`は決定論的な処理をMCP stdio serverとスタンドアロンCLIの両方から公開する。同じ
ライブラリと結果Schemaを使い、Skill、MCP adapter、CLI adapterへ判定ロジックを複製しない。

### 3. 実行体の配布

GitHubマーケットプレイスをAI利用者向けの主要な発見・導入経路とする。`bitz-core`プラグインは
`mcp.json`と起動境界を所有し、対応環境で自己完結実行体を同梱できる構造にする。Python + PyPI + `uv`の
スタンドアロン配布は、CI、非LLM利用、自己完結実行体を提供しない環境の明示的な代替経路として維持する。

プラグインは初回起動時を含め、Core、Python、依存パッケージを動的取得または自動更新しない。
自己完結実行体を提供できない環境では、外部`bitz`実行体の不足を`doctor`で`blocked`として案内する。

### 4. 互換性と`doctor`

プラグイン間依存の自動解決を標準へ期待しない。各拡張は自身のプラグインID、版、要求するCore API範囲、
Capabilityを実行前に`bitz doctor`または`bitz_doctor`へ渡す。`doctor`を互換性判定の正本とし、次を検査する。

- Core実行体とMCP serverの利用可否
- Core API、EARS-AI、Profileの版互換性
- `context.v1`、`check.v1`、`verify.v1`、`monorepo.v1`など要求Capabilityの有無
- `.spec/`、設定、検証コマンド、キャッシュの利用可否

不在または非互換時は`blocked`と具体的な導入・更新手順を返し、SkillがCore処理を代替しない。
Core自体が存在せず`doctor`を呼べない場合だけ、拡張の静的な導入案内を使用する。

Agent Plugins 1.0にはインストール済みプラグインを横断列挙する標準APIがないため、
`.spec/bitz.yaml`をインストール済みプラグイン台帳にしない。マーケットプレイスCIは全プラグインの
manifest、Core API要求、拡張間依存禁止、プラグイン外参照禁止を静的検査する。

### 5. リリース

マーケットプレイスカタログと各プラグインは同一リポジトリで管理し、リリースtagで整合した組合せを固定する。
各プラグインは独立にSemantic Versioningする。Core API majorの不一致は停止し、minor差は要求Capabilityが
満たされる限り許可する。外部リポジトリをsourceにする場合はtagだけでなくcommit SHAを固定する。

## Consequences

- 利用者は必要な機能だけを導入できる。
- EARS-AI解釈と品質判定の所有権を`bitz-core`へ集中できる。
- GitHub上の1カタログで発見性と版管理を統一できる。
- 標準にない依存自動解決を前提にしないため、クライアント差を`doctor`とCIで吸収する必要がある。
- 自己完結実行体の対象OS、アーキテクチャ、サイズは実証してから出荷範囲を確定する必要がある。

## Alternatives

### 単一の巨大プラグイン

導入は単純だが、利用しないProfile、Skill、クライアント固有機能まで配布され、権限面と更新影響が広がる。

### 拡張プラグイン間の依存

Agent Plugins 1.0の標準manifestで解決できず、クライアント固有の依存機能へ構成全体が拘束される。

### 共有ファイルを兄弟プラグインから参照

各プラグインが別ディレクトリへコピーされる配布モデルと整合せず、インストール先推測と更新順序へ依存する。

### SkillによるCore処理の代替

自然言語層にParser、Context選択、合否判定が複製され、同一入力に対する再現性を失う。

## Notes

- [Agent Plugins Specification 1.0.0](https://agent-plugins.org/specification)
- [GitHub Copilot CLI plugin reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference)

関連文書: [01_共通アーキテクチャ.md](../01_共通アーキテクチャ.md), [03_CLI統合設計.md](../03_CLI統合設計.md), [06_運用設計.md](../06_運用設計.md), [07_セキュリティとガバナンス.md](../07_セキュリティとガバナンス.md), [08_実装ロードマップ.md](../08_実装ロードマップ.md), [ADR-009](ADR-009_小規模チーム向け軽量コアとEARS-AI中核化.md)

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-08-27 | 初版を作成 | — |
| 2026-08-31 | Frontmatterと固定H2構成へ移行 | `ADR-020` |
