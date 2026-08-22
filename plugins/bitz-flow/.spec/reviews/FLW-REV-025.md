---
id: FLW-REV-025
title: "FLW-DSN-017 v2.0 Local Safety Profile再レビュー"
status: active
version: 1.0
updated: 2026-08-22
owner: codex
decision: PASS
---

# 設計レビュー統合レポート — FLW-DSN-017 v2.0 Local Safety Profile

- **review_id**: FLW-REV-025
- **対象**: FLW-DSN-017 v2.0、FLW-NFR-014 v2.0、FLW-FR-006 v2.0、FLW-TSK-106〜114、関連discovery・裁定
- **判定**: **PASS**
- **集計スコア**: **4.45 / 5.00**（PASS ≥ 3.5 / CONDITIONAL_PASS ≥ 2.5）
- **Design Gate**: 再裁定へ提出可能。Gate通過そのものは人間裁定を要する

## 観点別スコア

| 観点 | スコア | 重み | 主要所見 |
|---|---:|---:|---|
| consistency | 4.70 | 0.15 | 裁定・scope・要件・設計・taskが同じLocal Safety Profileへ収束 |
| data-integrity | 4.60 | 0.25 | 単一authority、緊急receipt、単一bundleで完全性境界を閉鎖 |
| operations | 4.20 | 0.20 | ローカルCLIに必要なdoctor/audit/reconcileへ運用面を限定 |
| risk | 4.33 | 0.25 | 単一hostとして再正規化。promotion/apply競合とcrashをfail-closed化 |
| business | 4.50 | 0.15 | 過剰設計を除外し小規模チームの通常運用へ回帰 |

findings: 統合前1件 → 重複排除後1件（P0: 0 / P1: 0 / P2: 0 / P3: 1）

## 総括

FLW-REV-024のP1 8件は、単一TargetTransaction、owner-only stagingとatomic promotion、
mutation前緊急receiptの追加、および署名policy・archive・RBAC・RTOのscope除外で解消された。
旧レビューのP2/P3もcase-aware collision key、2階層command、明示的scope裁定へ反映済みである。

Local Safety Profileは、同一OSユーザーとlocal filesystemを信頼し、複数processの通常競合・crashを
安全側へ止めるという製品実態に合う。service向け運用機構を追加せず、既存のM0縮退境界も維持している。

## P0 — Blocker

なし。

## P1 — Must Fix

なし。

## P2 — Should Fix

なし。

## P3 — Consider

- **SYN-001** [BIZ-401] 縮退後の実装予算は再校正待ち。
  - Design Gate通過後、実装再開前に9タスクのPR/session見積りを更新する。
  - **後続解消**: FLW-DSN-017 v2.1 §9.1とROADMAPへ6 PR/20 sessionの内訳・停止条件を反映し、
    FLW-REV-026で解消確認した。

## FLW-REV-024の解消確認

- P1 8件: **8件解消**。単一authority、promotion競合、release縮退、署名・archive除外、
  緊急receipt、bundle activationを再検査した。
- P2 3件: **3件解消**。case collision、OS owner境界、2階層commandを確認した。
- P3 1件: **scope外として解消**。RTOをLocal Safety ProfileのGate条件にしない。
- carried_over: **0件**。

## 人間への裁定依頼

本レビューはDesign Gateの**PASS推薦**である。`FLW-DSN-017` v2.0、`FLW-NFR-014` v2.0、
`FLW-FR-006` v2.0を対象にDesign Gateを再裁定し、通過後に実装予算を再校正することを推奨する。
