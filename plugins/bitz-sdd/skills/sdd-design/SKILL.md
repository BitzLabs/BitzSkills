---
name: sdd-design
description: BitzSDD の設計工程を行うスキル。ドメインストーリー、ドメインモデル（DDD 戦略設計・集約・境界づけられたコンテキスト）、API 設計（3層）、アーキテクチャ統合（3ビュー + 技術適合性評価）を確立し、成果物を .spec/design/ 内に記述・作成する。docs/02-design/ 側へは sdd-docs の pull コマンドを用いて同期・展開する。
metadata:
  version: "0.2.1"
  author: br7.hide
  created: "2026-07-08"
  updated: "2026-07-10"
---

# SDD Design — 設計工程

BitzSDDにおける設計フェーズを担当します。
ドメインストーリー、ドメインモデル、API設計、アーキテクチャの定義を `.spec/design/` 配下に直接作成・記述し、最終的に `sdd-docs` スキルの同期（pull）機能で `docs/02-design/` へ展開します。

## 1. 前提
*   作業台帳は `assets/design-worksheet.md` をコピーして `.spec/design/worksheet.md` として使用します。
*   設計成果物は `.spec/design/` の配下に直接作成・修正します。

## 2. 絶対規則
*   **設計は統合であって発明ではない**: 図のすべての構成要素は既存の設計要素（エンティティ・コンテキスト・API・要件）に対応させます。根拠のない構成要素はギャップとして明示します。
*   設計中に要件の矛盾や追加要件を見つけた場合は、`.spec/spec-issues/` に起票します。
*   **ID体系とFrontmatter**: マスターファイルは `DSN-NNN` のIDを持ち、必ず共通のYAML frontmatterを含めて作成します。

## 3. 判断分岐 — グリーンフィールド vs ブラウンフィールド
*   **グリーンフィールド (新規開発)**: story → domain → api → architecture
*   **ブラウンフィールド (既存刷新)**: 現状分析 → MMI/DDD 評価 → 統合改善計画 → 再設計

## 4. 成果物定義と同期

| # | ステップ | 成果物 (マスターファイル) | docs/ 同期先 |
|---|---|---|---|
| 1 | ドメインストーリー | `.spec/design/stories/` | `docs/02-design/domain-story.md` (自動集約) |
| 2 | ドメインモデル | `.spec/design/domain-model.md` | `docs/02-design/domain-model.md` |
| 3 | API 設計 | `.spec/design/api-design.md` | `docs/02-design/public-api.md` |
| 4 | アーキテクチャ統合 | `.spec/design/architecture.md` | `docs/02-design/ARCHITECTURE.md` |

設計成果物を作成・更新したら、`python3 scripts/sdd_sync.py pull` を実行して `docs/` に展開します。

## 5. Design Gate への接続
1.  マスターである `.spec/design/` の設計成果物が揃ったら、`sdd-review` で多観点レビューを実行します。
2.  レビュー判定（PASS / CONDITIONAL_PASS / FAIL）が `.spec/reviews/` に格納されます。
3.  レビュー判定結果を添えて、人間に Design Gate 裁定（docs側の active 化）を依頼します。
4.  承認されたら、`bitz-sdd` の要件駆動実装・検証フェーズへ移行します。
