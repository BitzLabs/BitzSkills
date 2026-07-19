---
id: SDD-REV-003
title: "frontmatter境界を保持する本文同期の設計レビュー"
status: active
version: 1.0
updated: 2026-07-19
owner: codex
decision: PASS
---

# SDD-REV-003 frontmatter境界を保持する本文同期の設計レビュー

- **review_id**: SDD-REV-003
- **対象**: SI-SDD-010 / SDD-FR-135 / SDD-DSN-003 / SDD-FR-100 / SDD-FR-126 / SDD-FR-128
- **判定**: **PASS**
- **集計スコア**: 4.69 / 5.00
- **対象外**: data-integrity（DB・永続データスキーマを扱わないため）

## 観点別スコア

| 観点 | スコア | 重み（正規化後） | 主要所見 |
|---|---:|---:|---|
| consistency | 5.00 | 0.20 | Issue→要件→設計と既存同期契約の境界が一貫 |
| operations | 4.80 | 0.27 | 原子的置換・非0終了・mtime維持。部分成功は再実行で収束 |
| risk | 4.33 | 0.33 | 非分散として縮退。バッチ途中失敗の明示が必要 |
| business | 4.85 | 0.20 | strict不整合を解消。push先欠如の挙動差を文書化 |

findings: 統合前3件 → 重複排除後2件（P0: 0 / P1: 0 / P2: 0 / P3: 2）

## P0 — Blocker

なし。

## P1 — Must Fix

なし。

## P2 — Should Fix

なし。

## P3 — Consider

- 複数ファイル同期で部分成功が起きた場合、成功・失敗件数と再実行要求を表示する。
- pushは既存`.spec`本文への逆反映であり、同期先欠如時はエラーになることをSKILL.mdへ記載する。

## 人間への裁定依頼

critical / major findingはなく、P3は実装・利用手順へ取り込む計画がある。
SDD-FR-135のapproved化とSDD-DSN-003のDesign Gate通過を推奨する。
