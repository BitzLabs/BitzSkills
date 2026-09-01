# Bitz AI-SDD Core 1.0設計

## 1. 目的

個人から数人のチームがAI CLIを利用するとき、仕様の取り違え、参照切れ、検証漏れ、危険な自動変更を
少ない待ち時間で防ぐ。

EARS-AIと単一workspaceの`.spec/`を、人間、AI、testが共有する小さな契約面とする。

## 2. 中心価値

EARS-AIは自然言語要求へ安定ID、actor、発動条件、規範強度、期待結果を付与する。人間が読め、Parserが
決定論的に構造化でき、必要な制約をContextとしてAIへ渡せることを価値とする。

保証するのは構文、参照、型付き依存、機械検査可能なtraceとtest実行である。自由記述の意味的正しさ、
LLM出力の決定論性、実装の完全性は保証せず、人間reviewとtestで補う。

## 3. 原則

1. Core 1.0は単一workspaceの垂直スライスに集中する。
2. 既定処理はlocal、offline、決定論的にする。
3. 強い依存を完全解決し、部分Contextを成功扱いしない。
4. 全`MUST`句とtest対応を追跡する。
5. LLM評価を必須の合否に使わない。
6. Gitを変更履歴、review、監査の正とする。
7. SPEC本文からcommandと権限を取得しない。
8. 成功時の出力と保存物を最小化する。
9. 1規則1正本とし、ADRを現行契約の正本にしない。
10. 実測で必要性を確認してから拡張を追加する。

## 4. 公開操作

| 操作 | 役割 |
|---|---|
| `bitz context` | 完全依存解決、Constraint Ledger、coverage、Context Digest |
| `bitz check` | EARS-AI、Schema、ID、関係、trace、Git差分の検査 |
| `bitz verify` | statement対応test commandの実行 |
| `bitz doctor` | 導入、設定、互換性、環境の診断 |

## 5. 文書一覧

| 文書 | 内容 |
|---|---|
| [01_システム構成.md](01_システム構成.md) | component、依存、公開操作、scope |
| [02_品質属性と安全境界.md](02_品質属性と安全境界.md) | 品質、性能、脅威、最小権限 |
| [03_SDDフロー.md](03_SDDフロー.md) | Small/Full/Spikeと完了条件 |
| [04_運用手順.md](04_運用手順.md) | 導入、日常操作、CI、復旧 |
| [05_ユースケース.md](05_ユースケース.md) | 公開操作とフローの受入シナリオ |
| [10_決定記録](10_決定記録/README.md) | 判断理由と代替案の履歴 |
| [Core 1.0詳細設計](../03.詳細設計/README.md) | 機械契約の正本 |
| [Core 1.0実装計画](../04.提案資料/12_Core-1.0実装計画.md) | 非規範の実装順序と実証条件 |

旧`01_共通アーキテクチャ.md`〜`09_ユースケース設計.md`は旧link維持用の移転案内であり、規範ではない。

## 6. Core 1.0対象外

- 複数`.spec/`のモノレポ連合、修飾ID、`--all-workspaces`
- ID衝突の勝敗判定と自動改番候補
- Profile Manifest、外部Validator、Profile固有Serializer／migration
- 必須Revision History
- 文書単位hashとProjection Digestの公開
- 厳格なMarkdown H2順序・空節style検査
- LLM意味監査、DDD、自動逆同期
- 永続run、承認service、workflow engine
- 複数Git repository、network越しSPEC

対象外機能は[ADR-039](10_決定記録/ADR-039_Core-1.0仕様構造の再編とscope縮小.md)の再評価条件に従い、
実測と新しいADRなしにCoreへ戻さない。
