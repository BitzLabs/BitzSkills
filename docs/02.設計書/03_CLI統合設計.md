# CLI統合設計

## 1. 方針

AIクライアント統合は薄く保つ。`bitz-core`がEARS-AIの解釈と判定を所有し、各クライアント向けスキルは
コマンド呼出し、対象範囲の選択、結果説明だけを担当する。

基本パッケージ形式はAgent Plugins 1.0.0とする。Core 1.0は主要クライアントを1つだけ参照実装し、
2つ目はSkillsとMCP契約の移植性を確認する最小試験に限定する。

## 2. 配布

| パッケージ | 内容 | 必須性 |
|---|---|---|
| `bitz-core` | MCP/CLI、EARS-AI Parser、context、check、verify、doctor | 必須 |
| `bitz-sdd` | Small Flow、SDD Profile、タスク分解 | 推奨する基本拡張 |
| `bitz-quality` | 品質レビュー、テスト十分性、LLM advisory | 需要確認後の拡張 |
| `bitz-ddd` | DDD Profileとドメインモデリング | 需要確認後の拡張 |
| `bitz-sync` | 仕様・実装差分と改訂候補 | 需要確認後の拡張 |

GitHubでホストする1つのマーケットプレイスリポジトリに各プラグインの自己完結ディレクトリを置き、
利用者が個別に導入できるようにする。各ルート`plugin.json`はAgent Plugins 1.0.0 schemaを宣言し、
Skillsは`skills/`、MCP設定は`mcp.json`へ置く。クライアント固有機能はreverse-domain namespaceへ隔離する。

`bitz-core`は対応環境で自己完結実行体を同梱できる構造とする。PyPI + `uv tool install bitz`は、CI、
非LLM利用、自己完結実行体を提供しない環境の明示的な代替経路として維持する。プラグインがCoreや依存を
動的取得または自動更新してはならない。詳細は[ADR-016](10_決定記録/ADR-016_Agent-Plugins準拠の複数プラグイン配布.md)を正とする。

## 3. 公開操作

```text
bitz context <spec-or-statement-id>... [--purpose interpret|implement|verify]
  [--format markdown|json] [--detail compact|standard|full]
  [--expand <document-id>[#revision-history]]... [--expect-digest sha256:<hex>]
  [--workspace <workspace-id>]
bitz check [ids-or-paths...] [--full] [--workspace <workspace-id>]
  [--format text|json] [--report]
bitz check --all-workspaces [--format text|json] [--report]
bitz verify [spec-or-statement-id|paths...] [--workspace <workspace-id>]
  [--format text|json] [--report]
bitz verify --all-workspaces [--format text|json] [--report]
bitz doctor [--workspace <workspace-id>|--all-workspaces] [--format text|json]
  [--plugin <id> --plugin-version <semver>]
  [--require-core-api <range>] [--require-capability <name>]...
```

`doctor`の検査順序、初回導入支援、Git不在時の縮退、Diagnosticは
[doctor仕様](../03.詳細設計/02_SPECファイル規定/11_doctor仕様.md)を正とする。

初期化はテンプレートのコピーまたはスキルで行い、専用CLIサブシステムを必須にしない。
SDD、DDD、同期はCore 1.0の公開コマンドへ含めない。

モノレポでは最寄りの`.spec/bitz.yaml`をactive workspaceとする。別workspaceの起点は
`<workspace-id>::<document-id>`で指定でき、`--workspace`はローカルIDと設定の解決基準を明示する。
`--all-workspaces`は連合ルートでの`check`、`verify`、`doctor`だけに使用し、`context`へは指定しない。
`--workspace`とは排他的であり、全体`check`は`--full`、全体`verify`は各workspaceの引数なしverifyを含意する。
詳細は[モノレポSPEC連合仕様](../03.詳細設計/02_SPECファイル規定/12_モノレポSPEC連合仕様.md)を正とする。

## 4. プラグイン責務

- Gitルート、active workspace、連合カタログと`.spec/`の検出
- 実装前のContext Bundle取得と、編集直前のContext Digest再照合
- Constraint Ledgerの全`MUST`確認と、必要な`reference`文書だけの明示展開
- コアコマンドの呼出し
- 読取り、書込み、コマンド実行の承認仲介
- stdout、stderr、終了コードの提示
- CLI固有形式への短い説明
- 拡張開始時の`doctor`プリフライトと要求Capabilityの提示

プラグインはEARS-AI、依存関係、Context選択を独自解析せず、合否や重大度を変更しない。拡張は
`bitz-core`だけへ依存し、別の拡張プラグインを必須依存にしない。別プラグインのファイルを相対パス、
symlink、インストール先推測で参照しない。

## 5. 能力不足時

| 能力 | 不足時の動作 |
|---|---|
| ファイル読取り | `blocked` |
| コマンド実行 | `context`と`check`だけ利用し、`verify`は`blocked` |
| ファイル書込み | 読取り専用で継続 |
| 対話承認 | 副作用を実行せず、実行候補を表示 |
| subagents | 同一エージェントで継続。独立監査を装わない |
| hooks | 使用しない |

別Agentや別コンテキストによるレビューは任意である。同一モデルを分離しただけのレビューを、
組織的に独立した監査として扱わない。

## 6. フック

Core 1.0はフックなしで完結する。フックは性能、互換性、攻撃面を増やすため既定で無効とし、
明示コマンドで解決できない実例が複数確認されるまで導入しない。

## 7. Core・プラグイン不在と版不整合

- 拡張は開始時に自身のID、版、要求Core API、要求Capabilityを`doctor`へ渡す。
- Core不在時は`blocked`と`bitz-core`の導入手順を返す。`doctor`自体を呼べない場合だけ静的案内へ縮退する。
- プラグインがコアを自動ダウンロードまたは更新しない。
- Core API major不一致または要求Capability不足は`blocked`とする。
- minor版差は要求Capabilityが満たされる限り許可する。
- Agent Plugins標準に横断的な導入済み一覧がないため、`.spec/bitz.yaml`をプラグイン台帳にしない。

## 8. 互換性試験

- クリーン環境での`uv tool install`
- 同一EARS-AI fixtureから同一Semantic IRとDiagnosticを得る
- 同一依存グラフから同じContext BundleとDigestを得る
- detailを変更しても解決集合とContext Digestは不変で、Projection Digestだけが変わる
- 参照漏れ、循環、上限超過で部分bundleを成功扱いしない
- コア不在時の`blocked`
- `check`がネットワーク、LLM、フックなしで動く
- CLIアダプターが判定を変更しない
- 全`plugin.json`と`mcp.json`がAgent Plugins 1.0.0 schemaへ適合する
- `bitz-core`以外への必須依存とプラグイン外ファイル参照がない
- 拡張ごとの`doctor`プリフライトが不在、非互換、Capability不足を`blocked`にする
- 同名のローカルIDを持つ複数workspace、横断依存、未登録member、所有境界違反のfixtureが正しく判定される
- `--all-workspaces`の結果順と集約statusが同一入力で再現される
