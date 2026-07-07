---
name: sdd-design
description: BitzSDD の設計工程を行うスキル。ドメインストーリー、ドメインモデル（DDD 戦略設計・集約・境界づけられたコンテキスト）、API 設計（System/Process/Experience 3層）、アーキテクチャ統合（3ビュー + 技術適合性評価）を確立し、docs/02-design/（ARCHITECTURE・domain-model・public-api・ADR）の proposed ドラフトを生成する。既存コードベースには MMI・DDD 12基準評価で現状を採点し改善計画を作る。「アーキテクチャを設計して」「ドメインモデルを作って」「APIを設計して」「境界づけられたコンテキスト」「既存コードを評価して」「マイクロサービス化できるか」と言われたとき、または bitz-sdd の Discuss フェーズで docs/02-design/ が未確立のときに使用する。設計レビューは sdd-review、要件化（EARS・採番）は bitz-sdd の管轄。
metadata:
  version: "0.1.0"
  author: br7.hide
  created: "2026-07-08"
  updated: "2026-07-08"
---

# SDD Design — 設計工程

docs/02-design/ 層のコンテンツを人間と協働で確立する。成果物は **proposed ドラフト**として書き、active 化（Design Gate）と要件派生は bitz-sdd スキルの管轄。

## 前提

- docs/ が初期化済みであること（未整備なら先に `sdd-docs` で初期化する）
- 上流の docs/01-context/（ビジョン・ペルソナ等）があれば設計の根拠として読む（未確立なら `sdd-discovery` を先に提案する）

## 絶対規則

- docs/ に書けるのは `status: proposed` のドラフトのみ。active 文書は書き換えない
- 要件（FR/NFR/CON）の採番はしない。設計中に要件の矛盾を見つけたら `.planning/spec-issues/` に起票する
- 手法の作業成果物（コンテキストマップ・CRUD 表・評価採点表・技術適合性マトリクス）は `.planning/design/` に置き、**人間向けの結論だけ**を docs/ のドラフトに落とす
- 設計は**統合であって発明ではない**。図のすべての構成要素は既存の設計要素（エンティティ・コンテキスト・API・要件）に対応させる。根拠のない構成要素はギャップとして明示する（能力を発明しない）

## 判断分岐 — 最初に決める

| 状況 | パス |
|---|---|
| 新規（実装がまだない/僅か） | **グリーンフィールド**: story → domain → api → architecture |
| 既存コードベースの刷新・評価 | **ブラウンフィールド**: 現状分析 → MMI/DDD 評価 → 統合改善計画 → 再設計 |

## グリーンフィールド・ワークフロー

各ステップで対応する reference を読んでから作業する:

| # | ステップ | 読むファイル | 成果物 |
|---|---|---|---|
| 1 | ドメインストーリー（ペルソナ×ジョブのハッピーパス） | references/domain-story.md | `.planning/design/stories/`（結論は domain-model ドラフトの根拠に） |
| 2 | ドメインモデル（2パス導出・集約・コンテキスト分割） | references/domain-modeling.md | docs/02-design/domain-model.md（proposed） |
| 3 | API 設計（3層カタログ） | references/api-design.md | docs/02-design/public-api.md（proposed） |
| 4 | アーキテクチャ統合（3ビュー + 技術適合性） | references/architecture.md | docs/02-design/ARCHITECTURE.md（proposed）+ ADR ドラフト |

- 恒久的な設計判断（技術採用・境界の裁定）は ADR ドラフトにする。テンプレは対象リポジトリの `docs/02-design/decisions/ADR-template.md` をコピーする（`status: proposed` のまま）
- 作業台帳は assets/design-worksheet.md をコピーして `.planning/design/worksheet.md` として使う

## ブラウンフィールド・ワークフロー

1. **現状分析** — コード構造・モジュール一覧・ドメイン対応表を `.planning/design/analysis/` にまとめる
2. **MMI / DDD 評価** — references/brownfield-evaluation.md を読み、2評価を並列実行して assets/evaluation-scorecard.md の書式で採点する
3. **統合改善計画** — 両評価で低スコアの領域を最優先に、quick wins（短期）と構造改善（中長期）に分類する
4. **再設計** — 改善計画を踏まえてグリーンフィールドの手順 2〜4 で目標設計を作る

既存コードからの要件の逆導出（reverse-derived）は `bitz-sdd` スキル（ブラウンフィールド導入の規約）の管轄。評価はその前段の「どこから手を付けるか」を決める材料になる。

## Design Gate への接続

1. ドラフト一式（proposed）が揃ったら `sdd-review` で多観点レビューを実行する
2. レビュー判定（PASS / CONDITIONAL_PASS / FAIL）を添えて人間に Design Gate 裁定（proposed → active 化）を依頼する
3. active 化されたら bitz-sdd スキルの半自動派生（docs/ → requirements/ draft）へ進む

## 連携

- 上流探索（ビジョン・ペルソナ・スコープ）は `sdd-discovery`、docs/ の初期化・構造検証は `sdd-docs`
- インフラ・セキュリティ・SLO・DR の設計は `sdd-infra`
- レビューは `sdd-review`、要件・タスク・検証の規律は `bitz-sdd`

## 出典

本スキルの手法群は [nexus-architect](https://github.com/wfukatsu/nexus-architect)（MIT License, Copyright (c) 2026 Wataru Fukatsu）の設計系スキル（map-domains / define-data-model / create-domain-story / design-api / design-architecture / evaluate-mmi / evaluate-ddd / integrate-evaluations）から DB 固有部分を除いて翻案・圧縮したもの。
