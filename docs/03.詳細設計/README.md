# Core 1.0 詳細設計

## 1. 規範性

本ディレクトリはCore 1.0の機械契約の正本である。ADRは判断理由、`docs/02.設計書`は目的と境界、
`docs/04.提案資料`は検討履歴であり、実装時の規範値は本ディレクトリを使用する。

矛盾時は次の所有境界に従う。

1. 共通status、Diagnostic、report、安全な入出力: `00_共通契約`
2. EARS-AI字句、構文、Semantic IR: `01_EARS-AI`
3. workspace、設定、文書、状態、関係、trace: `02_SPECモデル`
4. CLI/MCP入力、対象選択、操作結果: `03_操作仕様`

ADRを読まなければ実装できない契約を本仕様へ残してはならない。

## 2. Core 1.0 scope

Core 1.0は単一workspaceと、同一Git repository内の明示的なモノレポ連合を対象とし、次を提供する。

- EARS-AI ParserとSemantic IR
- `.spec/`文書モデルと型付き依存
- 完全ContextとContext Digest
- `context`、`check`、`verify`、`doctor`
- Git差分保護とtest command実行
- workspace修飾ID、所有境界、横断Context、全体検査・検証

複数Git repositoryの連合、自動改番、Profile実行基盤、Projection Digest、必須Revision Historyは対象外である。

## 3. 文書一覧

| 区分 | 文書 | 所有する契約 |
|---|---|---|
| 共通 | [結果・Diagnostic・終了コード](00_共通契約/01_結果・Diagnostic・終了コード.md) | status、共通結果、Diagnostic、report |
| 共通 | [安全な入出力・互換性](00_共通契約/02_安全な入出力・互換性.md) | I/O、上限、Git縮退、cache |
| 言語 | [言語・Semantic IR仕様](01_EARS-AI/01_言語・Semantic-IR仕様.md) | EARS-AI構文、Parser、IR |
| 言語 | [適合性・移行仕様](01_EARS-AI/02_適合性・移行仕様.md) | version、適合、旧版移行 |
| 言語 | [例・アンチパターン](01_EARS-AI/03_例・アンチパターン.md) | 記述例 |
| SPEC | [workspace・設定仕様](02_SPECモデル/01_workspace・設定仕様.md) | 探索、配置、`bitz.yaml` |
| SPEC | [文書・Frontmatter・状態仕様](02_SPECモデル/02_文書・Frontmatter・状態仕様.md) | 共通field、状態遷移 |
| SPEC | [文書種別・本文テンプレート](02_SPECモデル/03_文書種別・本文テンプレート.md) | REQ/TECH/ADR/TASK |
| SPEC | [関係・トレースモデル](02_SPECモデル/04_関係・トレースモデル.md) | 関係型、閉包、coverage、path |
| SPEC | [モノレポSPEC連合仕様](02_SPECモデル/05_モノレポSPEC連合仕様.md) | catalog、修飾ID、所有境界、横断解決、全体操作 |
| 操作 | [操作仕様](03_操作仕様/README.md) | 4操作の一覧と所有境界 |

## 4. 非目標

- 複数Git repository、Git submodule、network越しSPECの連合
- Profile Manifestと外部Validator
- 永続run、承認service、workflow engine
- LLMによる意味合否
- code symbolまたはassertion意味の自動trace
- DOCX、PDF、databaseを正本にする運用
