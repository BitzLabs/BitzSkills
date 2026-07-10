---
name: sdd-review
description: BitzSDD の設計ドキュメントや要件定義を多観点（consistency/data-integrity/operations/risk/business）で並列レビューするスキル。結果はすべて .spec/reviews/ 配下に格納し、レポート自動生成およびゲート判定の材料とする。
metadata:
  version: "0.2.2"
  author: br7.hide
  created: "2026-07-08"
  updated: "2026-07-11"
---

# SDD Review — 多観点並列レビュー

BitzSDDの設計と仕様の検証レビューを担当します。
`.spec/` ディレクトリに直接作成された仕様や設計（requirements, design）を対象にレビューを行い、その結果（PASS/CONDITIONAL_PASS/FAIL）を `.spec/reviews/` に格納します。

## 1. レビュー対象の決定
対象指定がない場合は、以下の優先順位で `.spec/` 配下から収集します：
1.  `.spec/design/**/*.md` (ドメインモデル、API、アーキテクチャ設計)
2.  `.spec/requirements/**/*.md` (機能・非機能要件)
3.  `.spec/discovery/**/*.md` (ディスカバリー成果物、business 観点の照合用)

## 2. 実行手順
1.  **レジストリ読み込み**: `assets/review-registry.json` を読み込む。プロジェクト側に `.spec/reviews/registry.json` があればそちらを優先。
2.  **並列起動**: 有効な観点ごとに `references/perspective-<name>.md` に従い、対象一覧に対するレビューを実行する。サブエージェントが利用できる場合は並列実行、それ以外は順次実行。
3.  **個別結果の保存**: 各観点の判定結果を `.spec/reviews/individual/<perspective>.json` に保存。
4.  **統合判定 (synthesis)**: 重複排除、P0〜P3 分類、重み正規化を行い、`.spec/reviews/review-synthesis.json` および統合報告書 `.spec/reviews/review-synthesis.md` を生成する。

## 3. 判定結果の扱いとライフサイクル
*   判定（`PASS` / `CONDITIONAL_PASS` / `FAIL`）は `sdd-report` による自動集計の対象となり、統合進捗レポート `.spec/reports/status-report.md` に反映されます。
*   `FAIL` または `CONDITIONAL_PASS` の場合は、指摘事項を修正するか、条件を消化するまで Design Gate / Promotion Gate を通過することはできません。
*   レビューで見つかった要件や設計の根本的な問題は、`.spec/spec-issues/` に起票します。
*   **ID体系**: 統合報告書 (`review-synthesis.md`) は `REV-NNN` のIDを持ち、YAML frontmatterを含みます。frontmatter には共通キーに加えて **`decision: PASS | CONDITIONAL_PASS | FAIL` を必須**で含めます（`sdd-report` の自動集計が参照する。書式の正は `sdd-core` の assets/artifact-frontmatter.md「領域固有の追加キー」）。Consistency観点の指摘事項は、制約要件(CON)との衝突を避けるため `RVC-` プレフィックスを使用します。
