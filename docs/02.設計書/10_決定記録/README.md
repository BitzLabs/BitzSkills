# 決定記録（ADR）

## 1. 目的

本ディレクトリは、設計上の重要な決定とその理由を追記型で保持する。設計書本文は「現在の決定内容」を述べ、ADRは「なぜその決定に至ったか」と「検討した代替案」を保持する。

実プロジェクトでは同種の記録を `.spec/decisions/` に置く。本ディレクトリは、Bitz AI-SDDプラグイン群自身の
開発に対する `.spec/decisions/` 相当物である。「相当」は目的と本文構造を指し、本ディレクトリ固有の
部分改訂ガバナンスまでCore共通契約として利用者へ課すことを意味しない。

## 2. 記載規則

- ADR IDは `ADR-001` 形式の連番とし、再利用・欠番の再割当てを禁止する。
- 各ADRはFrontmatter（`id`、`title`、`status`、`relations`）を持ち、状態は
  `proposed`、`accepted`、`rejected`、`superseded` とする。状態と後継関係はFrontmatterを正とする。
- H1は `# <id> <title>`、H2は `Context`、`Decision`、`Consequences`、任意の `Alternatives`、
  `Notes`、最終H2の `Revision History` とする。この固定構成は本ディレクトリだけのローカル規則であり、
  Core共通の本文構造要件ではない。
- 決定を変更する場合は既存ADRのDecisionを書き換えず、後継ADRを作成する。
- **全Decision項目が置き換わる場合**は、後継側の `relations.supersedes` に旧IDを書き、
  旧ADRの `status` を `superseded` にする。
- **一部のDecision項目だけが置き換わる場合**は部分改訂とし、旧ADRは `accepted` のままとする。
  `supersedes` / `superseded` は使わず、次の3点をすべて記録する
  （[ADR-033](ADR-033_部分改訂ADRの記録規約.md)）。
  1. 後継ADRのDecision本文へ、置き換える旧ADR IDとDecision項目、および他のDecisionを
     変更しないことを明記し、`relations.related` へ旧ADRを含める。
  2. 旧ADRの `Notes` へ、どのDecision項目がどの後継ADRへ移ったかを記載する。
  3. 旧ADRの `Revision History` へ1行追加し、Summaryへ対象Decision項目、
     Reference列へ後継ADR IDを書く。
- この部分改訂規約は`docs/02.設計書/10_決定記録/`に限定する。利用者の`.spec/decisions/`に対してCoreが
  認識する後継化は文書全体の置換だけであり、部分改訂の適用順序と3点記録を検査またはContextへ暗黙適用しない。
  Core保証内で既存Decisionを変更する場合は、現行Decisionを統合した後継ADRで文書全体を置換する。
- Decisionが番号付き箇条書きでないADRでは、Decision項目の代わりに該当箇所を一意に特定できる
  語句を用いる。番号を後付けするためにDecision本文を書き換えない。
- `x-amends` などのFrontmatter拡張キーと、`amends` 相当の新しい関係型は追加しない。
- 非意味的な訂正と後継化は、旧ADRの `Revision History` へ1行で要約する。
- 設計書本文の該当箇所からADRへリンクする。
- 本ディレクトリは `docs/` 配下の設計資料であり、`.spec/` の配置・命名・探索規則は適用しない。
  適用するのは本文構造規定だけである（[ADR-020](ADR-020_決定記録をSPEC本文構造規定へ適合させる.md)）。

## 3. 一覧

| ID | 題目 | 状態 | 関連文書 |
|---|---|---|---|
| [ADR-001](ADR-001_EARS-AI旧検討版の位置づけ.md) | EARS-AI旧検討版（v2/v3/v5）の位置づけ | accepted | EARS-AI規格/07 |
| [ADR-002](ADR-002_Gate語彙の所有権と診断のcheckpoint一般化.md) | Gate語彙の所有権と診断のcheckpoint一般化 | superseded | ADR-009 |
| [ADR-003](ADR-003_Diagnostic正本スキーマと診断コード命名規約.md) | Diagnostic正本スキーマと診断コード命名規約 | superseded | ADR-009, ADR-011 |
| [ADR-004](ADR-004_設定の上書き禁止分類.md) | 設定の上書き禁止分類 | superseded | ADR-009 |
| [ADR-005](ADR-005_規範文IDの階層と記法.md) | 規範文IDの階層と記法 | accepted | 02, EARS-AI規格/01 |
| [ADR-006](ADR-006_runIdの形式と並行実行制御.md) | runIdの形式と並行実行制御 | superseded | ADR-009 |
| [ADR-007](ADR-007_コア実行体の配布形態.md) | コア実行体の実装言語と配布形態 | superseded | ADR-009 |
| [ADR-008](ADR-008_プラグイン配布とコア実行体の入手経路.md) | プラグイン配布とコア実行体の入手経路 | superseded | ADR-009 |
| [ADR-009](ADR-009_小規模チーム向け軽量コアとEARS-AI中核化.md) | 小規模チーム向け軽量コアとEARS-AI中核化 | accepted | 01〜08, EARS-AI規格, ADR-010・011・016 |
| [ADR-010](ADR-010_型付き依存とContext-Resolutionの中核化.md) | 型付き依存とContext Resolutionの中核化 | accepted | 01〜05, SPECファイル規定/10 |
| [ADR-011](ADR-011_Diagnostic所有者とコード命名規約.md) | Diagnostic所有者とコード命名規約 | accepted | 01, EARS-AI規格/02・06, SPECファイル規定/06 |
| [ADR-012](ADR-012_置換済みREQ・TECHの適用禁止.md) | 置換済みREQ・TECHの適用禁止 | accepted | SPECファイル規定/03・04・10 |
| [ADR-013](ADR-013_文書IDとローカルIDの字句規則訂正.md) | 文書IDとローカルIDの字句規則訂正 | accepted | ADR-005, EARS-AI規格/01・08 |
| [ADR-014](ADR-014_Semantic-IRと段階的Context-Projection.md) | Semantic IRと段階的Context Projection | accepted | ADR-010, EARS-AI規格/06, SPECファイル規定/10 |
| [ADR-015](ADR-015_SPEC改訂履歴の必須化.md) | SPEC改訂履歴の必須化 | superseded | ADR-039 |
| [ADR-016](ADR-016_Agent-Plugins準拠の複数プラグイン配布.md) | Agent Plugins準拠の複数プラグイン配布 | accepted | 01, 03, 06〜08, SPECファイル規定/11 |
| [ADR-017](ADR-017_モノレポSPEC連合をCore-1.0へ含める.md) | モノレポSPEC連合をCore 1.0へ含める | superseded | ADR-039 |
| [ADR-018](ADR-018_正本Schemaの欠落補完と診断severityの明示.md) | 正本Schemaの欠落補完と診断severityの明示 | accepted | EARS-AI規格/01・02・06, SPECファイル規定/02〜04・06・11・12 |
| [ADR-019](ADR-019_検証対象と縮退判定の明確化.md) | 検証対象と縮退判定の明確化 | accepted | 03, EARS-AI規格/02, SPECファイル規定/02・06・11・12 |
| [ADR-020](ADR-020_決定記録をSPEC本文構造規定へ適合させる.md) | 決定記録をSPEC本文構造規定へ適合させる | accepted | ADR-015, SPECファイル規定/05・08 |
| [ADR-021](ADR-021_Diagnostic-severity・操作status・source-Schemaの分離.md) | Diagnostic severity・操作status・source Schemaの分離 | accepted | 01, EARS-AI規格/06, SPECファイル規定/06・10〜12 |
| [ADR-022](ADR-022_規範行候補抽出とID構文検証の分離.md) | 規範行候補抽出とID構文検証の分離 | accepted | EARS-AI規格/01・06, SPECファイル規定/04・06 |
| [ADR-023](ADR-023_verify明示対象とpath入力の確定.md) | verify明示対象とpath入力の確定 | accepted | 03, SPECファイル規定/06・10・12 |
| [ADR-024](ADR-024_SPEC文書の状態遷移契約.md) | SPEC文書の状態遷移契約 | accepted | 02, SPECファイル規定/03〜05 |
| [ADR-025](ADR-025_Git基準版とcheck明示対象の確定.md) | Git基準版とcheck明示対象の確定 | accepted | 01・03, SPECファイル規定/04・06・07 |
| [ADR-026](ADR-026_verify実行binding・timeout・結果Schemaの確定.md) | verify実行binding・timeout・結果Schemaの確定 | accepted | 01・03, SPECファイル規定/02・06・10・12 |
| [ADR-027](ADR-027_Diagnostic結果効果・集約・workspace-sourceの確定.md) | Diagnostic結果効果・集約・workspace sourceの確定 | accepted | 01, SPECファイル規定/06・10〜12 |
| [ADR-028](ADR-028_開発フローの実装後検査とTASK境界の接続.md) | 開発フローの実装後検査とTASK境界の接続 | accepted | 04・06・08・09, SPECファイル規定/05・06 |
| [ADR-029](ADR-029_TASK先行依存の状態ガード.md) | TASK先行依存の状態ガード | accepted | 09, SPECファイル規定/05・06・10 |
| [ADR-030](ADR-030_verify実行bindingの正規識別子と重複排除単位の統一.md) | verify実行bindingの正規識別子と重複排除単位の統一 | superseded | ADR-039 |
| [ADR-031](ADR-031_変更コード・テストからの検査対象選択.md) | 変更コード・テストからの検査対象選択 | accepted | 01・02・05, SPECファイル規定/06 |
| [ADR-032](ADR-032_ID再利用検出のCore保証範囲.md) | ID再利用検出のCore保証範囲 | superseded | ADR-037 |
| [ADR-033](ADR-033_部分改訂ADRの記録規約.md) | 部分改訂ADRの記録規約 | accepted | ADR-020, 決定記録README |
| [ADR-034](ADR-034_TASK完了終端とdone起点操作の確定.md) | TASK完了終端とdone起点操作の確定 | accepted | ADR-024・028・029, 04・06・08・09, SPECファイル規定/05・06・10 |
| [ADR-035](ADR-035_check空対象とフロー通過statusの確定.md) | check空対象とフロー通過statusの確定 | accepted | ADR-019・027・028・031・034, 01・04・05・08・09, SPECファイル規定/06 |
| [ADR-036](ADR-036_フロー取り止めと不採用履歴の保持.md) | フロー取り止めと不採用履歴の保持 | accepted | ADR-024・029・034, 04〜06・08・09, SPECファイル規定/03〜06・08・10 |
| [ADR-037](ADR-037_Git基準版間のSPEC同一性と削除規則.md) | Git基準版間のSPEC同一性と削除規則 | accepted | ADR-025・032・036, EARS-AI規格/01・06, SPECファイル規定/01・06・07・12 |
| [ADR-038](ADR-038_並行開発のID衝突解決と統合段階.md) | 並行開発のID衝突解決と統合段階 | superseded | ADR-039 |
| [ADR-039](ADR-039_Core-1.0仕様構造の再編とscope縮小.md) | Core 1.0仕様構造の再編とscope縮小 | accepted | 01〜09, 詳細設計全体, 提案11 |
| [ADR-040](ADR-040_モノレポSPEC連合をCore-1.0へ再導入する.md) | モノレポSPEC連合をCore 1.0へ再導入する | accepted | ADR-017・039, SPECモデル/05 |
| [ADR-041](ADR-041_verify対象別証跡とreport明示保存の分離.md) | verify対象別証跡とreport明示保存の分離 | accepted | ADR-019・026・039・040, 共通結果, verify仕様 |
