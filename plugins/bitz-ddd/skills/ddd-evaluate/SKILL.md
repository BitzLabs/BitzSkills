---
name: ddd-evaluate
description: BitzDDD — 既存コードベースの DDD 成熟度（12基準・3レイヤー）と MMI（Modularity Maturity Index）を採点し、統合改善計画に落とすブラウンフィールド評価スキル。ユーザーが「DDD 評価」「MMI」「成熟度評価」「ブラウンフィールド評価」「モジュール性を測って」「リファクタリング前の現状評価」に言及したとき、または sdd-design のブラウンフィールド分岐で成熟度評価が必要になったときに使用する。bitz-sdd プラグインとの併用が前提。
metadata:
  version: "0.2.0"
  author: br7.hide
  created: "2026-07-10"
  updated: "2026-07-21"
---

# DDD Evaluate — DDD / MMI 成熟度評価

既存コードベースの成熟度を2つの独立した枠組み（DDD 12基準 + MMI 4軸）で採点し、
統合改善計画に落とします。2評価は独立なので並列実行できます。

## 前提（bitz-sdd との契約）

*   本スキルは **bitz-sdd プラグインとの併用が前提**です。採点表は `.spec/design/evaluation/scorecard.md`、評価レポートは `.spec/reviews/` 配下に書き込みます。
*   前提として現状分析（モジュール一覧・ドメイン対応表）を `.spec/design/analysis/` に揃えておきます。

## 実行手順

1.  **統合プロセス**: `references/brownfield-evaluation.md` に従い、評価の全体フロー（現状分析 → 2評価の並列実行 → 統合改善計画）を回します。
2.  **DDD 成熟度**: `references/ddd-maturity.md` の12基準（Strategic（戦略設計）30% / Tactical（戦術設計）45% / Architecture（アーキテクチャ）25%）で採点します。
3.  **MMI**: `references/mmi-maturity.md` の4軸（Cohesion（凝集度）/ Coupling（結合度）/ Independence（独立性）/ Reusability（再利用性））でモジュールごとに採点します。
4.  採点は `assets/evaluation-scorecard.md` の書式で記録し、改善優先度トップ3〜5を導出して `sdd-design` の再設計工程（統合改善計画）へ引き渡します。
