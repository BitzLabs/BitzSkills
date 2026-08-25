# 決定記録（ADR）

## 1. 目的

本ディレクトリは、設計上の重要な決定とその理由を追記型で保持する。設計書本文は「現在の決定内容」を述べ、ADRは「なぜその決定に至ったか」と「検討した代替案」を保持する。

実プロジェクトでは同種の記録を `.spec/decisions/` に置く。本ディレクトリは、Bitz AI-SDDプラグイン群自身の開発に対する `.spec/decisions/` 相当物である。

## 2. 記載規則

- ADR IDは `ADR-001` 形式の連番とし、再利用・欠番の再割当てを禁止する。
- 状態は `Proposed`、`Accepted`、`Superseded`、`Rejected` とする。
- 決定を変更する場合は既存ADRを書き換えず、新しいADRを作成して `Superseded by` を追記する。
- 設計書本文の該当箇所からADRへリンクする。

## 3. 一覧

| ID | 題目 | 状態 | 関連文書 |
|---|---|---|---|
| [ADR-001](ADR-001_EARS-AI旧検討版の位置づけ.md) | EARS-AI旧検討版（v2/v3/v5）の位置づけ | Accepted | EARS-AI規格/07 |
| [ADR-002](ADR-002_Gate語彙の所有権と診断のcheckpoint一般化.md) | Gate語彙の所有権と診断のcheckpoint一般化 | Superseded | ADR-009 |
| [ADR-003](ADR-003_Diagnostic正本スキーマと診断コード命名規約.md) | Diagnostic正本スキーマと診断コード命名規約 | Superseded | ADR-009, ADR-011 |
| [ADR-004](ADR-004_設定の上書き禁止分類.md) | 設定の上書き禁止分類 | Superseded | ADR-009 |
| [ADR-005](ADR-005_規範文IDの階層と記法.md) | 規範文IDの階層と記法 | Accepted | 02, EARS-AI規格/01 |
| [ADR-006](ADR-006_runIdの形式と並行実行制御.md) | runIdの形式と並行実行制御 | Superseded | ADR-009 |
| [ADR-007](ADR-007_コア実行体の配布形態.md) | コア実行体の実装言語と配布形態 | Superseded | ADR-009 |
| [ADR-008](ADR-008_プラグイン配布とコア実行体の入手経路.md) | プラグイン配布とコア実行体の入手経路 | Superseded | ADR-009 |
| [ADR-009](ADR-009_小規模チーム向け軽量コアとEARS-AI中核化.md) | 小規模チーム向け軽量コアとEARS-AI中核化 | Accepted | 01〜08, EARS-AI規格 |
| [ADR-010](ADR-010_型付き依存とContext-Resolutionの中核化.md) | 型付き依存とContext Resolutionの中核化 | Accepted | 01〜05, SPECファイル規定/10 |
| [ADR-011](ADR-011_Diagnostic所有者とコード命名規約.md) | Diagnostic所有者とコード命名規約 | Accepted | 01, EARS-AI規格/02・06, SPECファイル規定/06 |
| [ADR-012](ADR-012_置換済みREQ・TECHの適用禁止.md) | 置換済みREQ・TECHの適用禁止 | Accepted | SPECファイル規定/03・04・10 |
| [ADR-013](ADR-013_文書IDとローカルIDの字句規則訂正.md) | 文書IDとローカルIDの字句規則訂正 | Accepted | ADR-005, EARS-AI規格/01・08 |
