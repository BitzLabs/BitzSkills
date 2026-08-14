---
id: QLT-REV-002
title: "レビュー基盤 仕様・設計レビュー（初回）"
status: pending
decision: CONDITIONAL_PASS
version: 1.0
updated: 2026-08-14
owner: br7.hide
---

# レビュー基盤 仕様・設計レビュー（初回）

- **review_id**: QLT-REV-002
- **対象**: `plugins/bitz-quality/.spec/discovery/`、`requirements/QLT-FR-017〜026`、`design/`、`SI-QLT-001`
- **判定**: **CONDITIONAL_PASS**
- **集計スコア**: 2.88

## 観点別スコア

| 観点 | スコア | 重み | 主要所見 |
|---|---:|---:|---|
| consistency | 3.65 | 0.15 | Gate現在地と仮説追跡を補正する |
| data-integrity | 2.25 | 0.25 | 並行実行と公開世代の整合性が不足 |
| operations | 3.70 | 0.20 | 中断復旧とraw log保護が不足 |
| risk | 2.00 | 0.25 | timeout、競合、TOCTOUが未契約 |
| business | 3.55 | 0.15 | 測定プロトコルの再現性が不足 |

findings: 統合前16件 → 重複排除後9件（P0: 0 / P1: 4 / P2: 3 / P3: 2）

## P1 — Must Fix

- **SYN-001** 原子的公開境界: immutable run directoryとcommit manifestを要件化する。
- **SYN-002** 並行attempt: 世代番号と単一writerでactive遷移を直列化する。
- **SYN-003** timeout収束: process group停止、quota、BLOCKED判定を要件化する。
- **SYN-004** digest/TOCTOU: canonical bytesと固定snapshotを契約化する。

## P2 — Should Fix

- Gate現在地と仮説トレーサビリティを更新する。
- raw logのredaction・権限・保持規則を追加する。
- 測定母集団、最低試行数、baseline比較方法を固定する。

## P3 — Consider

- run history・監査主体・移行ownerを実装計画へ含める。
- 設計台帳とPublished Languageを揃える。

## CONDITIONAL_PASS の通過条件

- [x] `QLT-REV-002:GP-001` 単一世代の原子的公開
- [x] `QLT-REV-002:GP-002` 並行attemptの世代制御
- [x] `QLT-REV-002:GP-003` timeout・資源上限後の有限時間収束
- [x] `QLT-REV-002:GP-004` canonical digestと固定snapshot

## 人間への裁定依頼

本判定だけではDesign Gateを通過しない。上記条件をdraft要件・設計へ反映し、再レビュー後に人間が裁定する。
