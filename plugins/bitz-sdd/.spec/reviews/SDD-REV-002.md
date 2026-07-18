---
id: SDD-REV-002
title: "日本語6章docsレイアウトと安全な移行の設計レビュー"
status: active
version: 1.0
updated: 2026-07-18
owner: codex
decision: PASS
---

# SDD-REV-002 日本語6章docsレイアウトと安全な移行の設計レビュー

- **review_id**: SDD-REV-002
- **対象**: SDD-DSN-002 / SDD-FR-125〜129 / SI-SDD-012
- **判定**: **PASS**
- **集計スコア**: 4.62 / 5.00
- **対象外**: data-integrity（DB・永続データスキーマを扱わないため）

## 観点別スコア

| 観点 | スコア | 重み（正規化後） | 主要所見 |
|---|---:|---:|---|
| consistency | 4.70 | 0.20 | 6章と英語areaの許容集合を単一表に固定する |
| operations | 4.50 | 0.27 | apply後のstrict検査とdiff確認を検収へ含める |
| risk | 4.67 | 0.33 | 全移動計画の一意性を変更前に検査する |
| business | 4.60 | 0.20 | major releaseと移行手順を明示する |

findings: 統合前4件 → 重複排除後4件（P0: 0 / P1: 0 / P2: 0 / P3: 4）

## P0 — Blocker

なし。

## P1 — Must Fix

なし。

## P2 — Should Fix

なし。

## P3 — Consider

- 章とareaの許容集合をdocs_inspectと運用規約の同一表で固定する。
- apply後に`docs_inspect.py --strict`と`git diff`を確認する。
- 移行元・移行先の重複および既存先衝突を変更前に一括検査する。
- semver major、移行ガイド、dry-run例をリリースノートへ明記する。

## 人間への裁定依頼

critical / major findingはなく、実装前提の補強はSDD-DSN-002へ反映済み。Design GateはPASSを推奨する。
