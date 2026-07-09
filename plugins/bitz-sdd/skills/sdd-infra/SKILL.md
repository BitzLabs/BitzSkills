---
name: sdd-infra
description: BitzSDD のインフラ・運用設計を行うスキル。インフラ構成、セキュリティ、可観測性・SLO、災害復旧、コスト見積もりを設計する。成果物はすべて .spec/design/ 配下に作成し、docs/05-operations/ 側などへは sdd-docs の pull コマンドを用いて同期・展開する。
metadata:
  version: "0.2.0"
  author: br7.hide
  created: "2026-07-08"
  updated: "2026-07-09"
---

# SDD Infra — インフラ・運用設計

BitzSDDにおけるインフラおよび運用の設計を担当します。
アーキテクチャ設計を前提に、運用面の設計（構成・セキュリティ・SLO・DR・コスト）を `.spec/design/` 内の成果物として記述・作成し、最終的に `sdd-docs` スキルの同期（pull）機能で `docs/05-operations/` などへ展開します。

## 1. 前提
*   作業成果物（サイジング、コスト見積もり内訳、セキュリティモデル等）は `.spec/design/` の配下に直接作成・修正します。
*   IaCコードなどの実装は行いません（それは要件→タスク→機械検証の通常の開発規律に乗せて行います）。

## 2. 絶対規則
*   数値目標（SLO、バックアップ頻度、コスト上限など）はでっち上げず、根拠のないものは `TBD` と明示します。
*   数値目標は検証可能な形式（p95/p99、期間、閾値の明示）で記述します。
*   **ID体系とFrontmatter**: マスターファイルは `INF-NNN` のIDを持ち、必ず共通のYAML frontmatterを含めて作成します。

## 3. 領域と成果物定義

| 領域 | 成果物 (マスターファイル) | docs/ 同期先 |
|---|---|---|
| インフラ構成 | `.spec/design/infrastructure.md` | `docs/05-operations/OPERATIONS.md` (インフラ部) |
| セキュリティ | `.spec/design/security-model.md` | `docs/02-design/security-model.md` |
| 可観測性・SLO | `.spec/design/observability.md` | `docs/05-operations/OPERATIONS.md` (可観測性部) |
| 災害復旧 (DR) | `.spec/design/dr.md` | `docs/05-operations/OPERATIONS.md` (DR部) |
| コスト見積もり | `.spec/design/cost-estimate.md` | - (レビュー/レポート集計対象) |

設計成果物を作成・更新したら、`python3 scripts/sdd_sync.py pull` を実行して `docs/` に展開します。

## 4. 連携
*   前段のドメイン・API・アーキテクチャ設計は `sdd-design`、レビューは `sdd-review`、要件・検証・ゲートは `bitz-sdd` が担当します。
*   ドキュメントの双方向同期や初期化は `sdd-docs` が担当します。
