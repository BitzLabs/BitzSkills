---
id: FLW-REV-026
title: "FLW-DSN-017 v2.1 運用受入・接続完全性再レビュー"
status: active
version: 1.0
updated: 2026-08-22
owner: codex
decision: PASS
---

# 設計レビュー統合レポート — FLW-DSN-017 v2.1

- **review_id**: FLW-REV-026
- **対象**: FLW-DSN-017 v2.1、FLW-NFR-014 v2.1、FLW-FR-006 v2.0、FLW-TSK-106〜114、ROADMAP
- **判定**: **PASS**
- **集計スコア**: **4.96 / 5.00**
- **findings**: P0 0 / P1 0 / P2 0 / P3 0
- **Design Gate**: 再裁定へ提出可能。Gate通過そのものは人間裁定を要する

## 観点別スコア

| 観点 | スコア | 重み | 主要所見 |
|---|---:|---:|---|
| consistency | 5.00 | 0.15 | 用語表、E2E接続、task依存が同じ語彙と境界で閉じた |
| data-integrity | 5.00 | 0.25 | read/write Git authorityと全crash pointの完全性条件が明確 |
| operations | 4.80 | 0.20 | 12行の運用受入条件とrunbook接続を定量化 |
| risk | 5.00 | 0.25 | 非分散次元をN/Aとし、残る障害経路を全てfail-closed化 |
| business | 5.00 | 0.15 | 9taskを6 PR/20 sessionへ再見積もりし停止条件まで確定 |

## 機能接続の確認

- root taskはFLW-TSK-106のみで、最終FLW-TSK-114から106〜113の全taskへ到達できる。
- task依存cycle、欠落dependency、未接続E2E edgeはいずれも0件。
- plan、apply、mutation、終了、audit、verify、reconcile、promotion、startup gateの9フローに所有taskがある。
- `audit`のGit観測経路はwrite-capable `MutationCoordinator`から分離したread-only
  `RepositoryObserver`で閉じ、既存の「運用CLIはGitを直接起動しない」制約と両立した。
- 12行の運用受入マトリクスは検出、永続状態、許可操作、復旧完了、受入値を一対一で持つ。

## 前レビューからの解消

FLW-REV-025の唯一のP3であった実装予算未校正は、9taskを基礎とする6 PR/20 session、PR別内訳、
停止条件、sunk cost分離をFLW-DSN-017とROADMAPへ反映して解消した。用語一貫性、トランザクション安全性、
運用即応性、障害モード、NFR定量化も、今回の成果物で設計上の不足を閉じた。

## 残余リスク

operationsのセキュリティ態勢は4点とする。同一OSユーザーを信頼するLocal Safety Profileでは適切だが、
悪意ある同一ユーザーへの改ざん耐性、RBAC、鍵管理を意図的に保証しないためである。これはfindingではなく
明示済みscope境界であり、点数目的でM2へ再導入しない。

## 人間への裁定依頼

`FLW-DSN-017` v2.1、`FLW-NFR-014` v2.1、`FLW-FR-006` v2.0を対象にDesign Gateを再裁定する。
承認後はFLW-DSN-017 §9.1のPR順と停止条件に従い、運用受入マトリクスをcoverage manifestとして実装する。
