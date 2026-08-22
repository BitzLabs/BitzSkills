---
id: FLW-REV-021
title: "approval-mode 宣言の完全性と plan/apply 束縛の設計レビュー"
status: active
version: 1.0
updated: 2026-08-22
owner: codex
decision: FAIL
---

# 設計レビュー統合レポート — approval-mode 宣言の完全性と plan/apply 束縛

- **review_id**: FLW-REV-021
- **対象**: FLW-NFR-013、FLW-DSN-017、SI-FLW-077、および worktree runtime / capability 実装
- **判定**: **FAIL**
- **集計スコア**: **2.49 / 5.00**（PASS ≥ 3.5 / CONDITIONAL_PASS ≥ 2.5）

## 観点別スコア

| 観点 | スコア | 重み | 主要所見 |
|---|---:|---:|---|
| consistency | 3.35 | 0.15 | 系譜と所有者用語の補正が必要 |
| data-integrity | 2.25 | 0.25 | 信頼根と原子境界が未定義 |
| operations | 2.50 | 0.20 | 監査証跡と移行規則が不足 |
| risk | 2.00 | 0.25 | プロセス間排他と旧形式拒否が不足 |
| business | 2.80 | 0.15 | 競合検証と既存契約への接続が不足 |

findings: 統合前 14 件 → 重複排除後 9 件（P0: 0 / P1: 5 / P2: 3 / P3: 1）

## 判定の根拠

宣言状態を閉集合化し、digestをplanとcapabilityへ束縛する方向性は妥当である。しかし最終再照合からGit mutationまでの置換を防げず、プロセス内だけのtarget guardは別CLI競合を直列化できない。さらにabsent状態の中間変化と、digestを持たない既存capabilityの拒否・移行規則が未定義である。

## P1 — Design Gate 前に解消する事項

- **FLW-REV-021:SYN-001**: 宣言再照合とGit mutationの原子境界を設計する。
- **FLW-REV-021:SYN-004**: 別CLIとcrash後を含む永続的なtarget排他を設計する。
- **FLW-REV-021:SYN-005**: absent状態の中間変化を識別するか、識別不能時に停止する。
- **FLW-REV-021:SYN-006**: capabilityのversion、旧形式拒否、pending operationの再計画・rollbackを定義する。
- **FLW-REV-021:SYN-008**: FLW-NFR-013の系譜を既存の承認モード契約へ訂正する。

## Gate 前提条件

`FLW-REV-021:GP-001`〜`GP-005` を消化し、改訂設計を再レビューするまで Design Gate は通過できない。過去レビューから未解消のP0/P1も `FLW-REV-021.json` の `carried_over` に継承した。

## 人間への裁定依頼

この判定は推奨であり、Design Gateの裁定ではない。要件系譜の訂正は承認済み要件の変更となるため、別途人間の裁定を要する。
