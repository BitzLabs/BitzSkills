---
id: FLW-REV-027
title: "M2 Local Safety Profile 実装後レビュー"
status: active
version: 1.0
updated: 2026-08-23
owner: codex
decision: FAIL
---

# M2 Local Safety Profile 実装後レビュー

- **対象**: FLW-DSN-017、FLW-FR-006、FLW-NFR-014、FLW-TSK-106〜114、
  flow-coreのCLI・platform・runtime・transaction・recovery・operability、関連schema・test・runbook
- **判定**: **FAIL**
- **集計スコア**: **2.12**（FAIL: 2.5未満。riskも1.33でfloor未達）
- **公開判断**: worktree operationは現在のgated状態を維持し、Promotion Gateを停止する

## 観点別スコア

| 観点 | スコア | 重み | 主要所見 |
|---|---:|---:|---|
| consistency | 2.65 | 0.15 | 設計・task完了・production入口の接続が不一致 |
| data-integrity | 2.00 | 0.25 | durable確定境界とrecovery authority間に不整合 |
| operations | 2.30 | 0.20 | 実環境probe・finite timeout・production E2Eが未接続 |
| risk | 1.33 | 0.25 | 正常経路断線、旧CLI契約、Windows identity |
| business | 2.85 | 0.15 | create/resumeの利用価値がproductionで未達 |

findings: 統合前23件 → 重複排除後10件（P0: 2 / P1: 5 / P2: 3 / P3: 0）。

## P0 — Blocker

- **SYN-001** 実環境platform evidenceからproduction CLIへの経路が無い
  - SI-FLW-084でOS別probe、doctor/plan共通evidence、3platform production E2Eを追跡する。
- **SYN-002** create/resume CLIが廃止済み承認契約と旧contextを参照する
  - SI-FLW-085でplan-digest専用CLIへ置換し、旧入力は解析せず即時拒否する。

## P1 — Must Fix

- **SYN-003** Git childの有限timeoutと30秒terminal resultが未実装 — SI-FLW-086
- **SYN-004** intentと緊急receiptのdurable確定間にcrash空隙がある — SI-FLW-087
- **SYN-005** QUARANTINED operationをconfirmed-completeへ誤分類できる — SI-FLW-088
- **SYN-006** reconcile closureがactive marker適格性の確認より先に追記される — SI-FLW-089
- **SYN-007** verified・task done・予算がproduction接続完了を過大主張する — SI-FLW-090

## P2 — Should Fix

- FLW-FR-006へcreate/resume是正taskを直接トレースし、finish/discardのM3境界を明示する。
- doctorとrunbookへplatform診断理由、責任分界、引継ぎ条件、再判定Gateを追加する。
- 過去レビューの未解決P0/P1 88件を実証ベースで再照合する（SI-FLW-091）。

## Gate blocking条件

1. SI-FLW-084〜SI-FLW-089のruntime・運用不整合を解消する。
2. production既定dispatcher、3platform実観測、全crash境界、finite timeoutをmachine evidenceへ残す。
3. SI-FLW-090でrequirement・task・検証仕様・予算を実態へ揃える。
4. 是正完了後に同じ5観点で再レビューし、**PASS**を得る。

## carried over台帳

過去9レビューの未解決P0/P1 **88件**を番号付きJSONのcarried_overへ収録した。
後続レビューで実質解消されている候補も、原記録のstatusが未更新なため機械台帳上は未解決である。
SI-FLW-091で削除せず証跡照合し、resolvedまたは現行issueへ追跡する。

## 裁定

ユーザーの指示により公開は停止する。これはPromotion Gate通過記録ではなく、是正開始のための
実装後レビューである。spec-issueはすべてopenであり、accept/rejectの最終裁定は人間専権を維持する。
