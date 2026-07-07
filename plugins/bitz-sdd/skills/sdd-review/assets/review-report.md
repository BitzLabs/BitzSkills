# 設計レビュー統合レポート

- **review_id**: <日付-連番>
- **対象**: <レビューしたファイル一覧 or feature 名>
- **判定**: **PASS | CONDITIONAL_PASS | FAIL**
- **集計スコア**: <aggregate>（PASS ≥ 3.5 / CONDITIONAL ≥ 2.5）

## 観点別スコア

| 観点 | スコア | 重み（正規化後） | 主要所見 |
|---|---|---|---|
| consistency | <n.nn> | <0.nn> | <1行> |
| data-integrity | <n.nn or 対象外> | <0.nn> | <1行> |
| operations | <n.nn> | <0.nn> | <1行> |
| risk | <n.nn> | <0.nn> | <1行> |
| business | <n.nn> | <0.nn> | <1行> |

findings: 統合前 <N> 件 → 重複排除後 <M> 件（P0: _ / P1: _ / P2: _ / P3: _）

## P0 — Blocker

- **SYN-001** [<source_ids>] <タイトル>
  - 場所: <file:節> / 問題: <1〜2文> / 是正: <実行可能な1項目>

## P1 — Must Fix

（同書式）

## P2 — Should Fix

（同書式・簡略可）

## P3 — Consider

（箇条書きのみ）

## CONDITIONAL_PASS の通過条件

（該当時のみ。各 critical/major への軽減策。STATE.md に転記して消化を追跡する）

- [ ] <条件1>

## 人間への裁定依頼

この判定は推奨です。Design Gate / Promotion Gate の裁定（proposed→active 化・通過）は上記を確認のうえ行ってください。
