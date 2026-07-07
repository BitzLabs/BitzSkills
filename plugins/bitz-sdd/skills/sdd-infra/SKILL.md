---
name: sdd-infra
description: BitzSDD のインフラ・運用設計を行うスキル。インフラ構成（コンテナ/ネットワーク/IaC 方針/マルチ環境）、セキュリティ（認証認可・シークレット・ゼロトラスト・監査）、可観測性（SLI/SLO・エラーバジェット・トレーシング・アラート）、災害復旧（RTO/RPO・バックアップ・ランブック）、コスト見積もりの5領域を設計ドキュメントとして確立する。「インフラを設計して」「セキュリティ設計」「SLO を決めたい」「監視・アラート設計」「DR・バックアップ」「コストを見積もって」と言われたとき、または sdd-design のアーキテクチャ確定後に運用面の設計が必要なときに使用する。IaC コードの生成は行わない（実装は bitz-sdd の要件・タスク規律で行う）。NFR の要件化・採番は bitz-sdd の管轄。
metadata:
  version: "0.1.0"
  author: br7.hide
  created: "2026-07-08"
  updated: "2026-07-08"
---

# SDD Infra — インフラ・運用設計

アーキテクチャ（docs/02-design/ARCHITECTURE.md、active または proposed ドラフト）を前提に、運用面の設計を確立する。**設計ドキュメントまで**が責務 — IaC コードの生成はしない（実装は要件→タスク→機械検証の規律に乗せるべき対象であり、生成でその規律を迂回しない）。

## 絶対規則

- docs/ に書けるのは `status: proposed` のドラフトのみ。active 文書は書き換えない
- 要件（NFR/CON）の採番はしない。数値目標は docs/ ドラフトに書き、要件化は Design Gate 後の bitz-sdd の派生に委ねる
- 根拠のない数値（SLO・容量・コスト単価）は発明せず `TBD` と明記する
- 詳細な作業表（サイジング・見積もり内訳）は `.planning/design/infra/` に置き、結論だけを docs/ ドラフトへ

## 5領域 — 必要な分だけ選択的に実行する

全領域を機械的に埋めない。feature とプロジェクトの段階に必要な領域だけ、対応する reference を読んでから設計する:

| 領域 | 読むファイル | 結論の行き先 |
|---|---|---|
| インフラ構成 | references/infrastructure.md | docs/05-operations/OPERATIONS.md（proposed）+ 恒久判断は ADR ドラフト |
| セキュリティ | references/security.md | docs/02-design/security-model.md（proposed） |
| 可観測性・SLO | references/observability.md | docs/05-operations/OPERATIONS.md（proposed） |
| 災害復旧 | references/disaster-recovery.md | docs/05-operations/OPERATIONS.md（proposed） |
| コスト見積もり | references/cost.md | `.planning/design/infra/cost-estimate.md`（短命。前提が固まったら ADR に要約） |

対象文書が対象リポジトリに未展開なら、`sdd-docs` の `_scaling.md` 拡張トリガーに従って先に足す（05-operations は「定期的にデプロイし再現可能な手順が要るとき」）。

## NFR への接続

SLO・エラーバジェット・RTO/RPO・セキュリティ統制の数値は、Design Gate で active 化された後に bitz-sdd の半自動派生で NFR になる（benchmark / load-test / sast / dep-audit、数値必須）。このスキルでは**検証可能な形**（p95/p99・期間・母集団・閾値の明示）で書くところまでを行い、採番・EARS 化はしない。実装済みシステムの数値要件に矛盾を見つけたら `.planning/spec-issues/` に起票する。

## 連携

- 前段のアーキテクチャは `sdd-design`、レビュー（operations / risk 観点）は `sdd-review`
- docs/ の構造・テンプレは `sdd-docs`、要件派生・ゲートは `bitz-sdd`

## 出典

本スキルの手法群は [nexus-architect](https://github.com/wfukatsu/nexus-architect)（MIT License, Copyright (c) 2026 Wataru Fukatsu）の design-infrastructure / design-security / design-observability / design-disaster-recovery / estimate-cost / design-sla / define-nfr から ScalarDB 固有部分を除いて翻案・圧縮したもの。
