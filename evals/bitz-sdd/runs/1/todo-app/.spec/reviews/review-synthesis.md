---
id: REV-001
title: "ToDo管理Webアプリ 設計統合レビュー"
status: active
version: 1.0
updated: 2026-07-11
owner: br7.hide
decision: CONDITIONAL_PASS
---

# 統合レビュー結果

対象: `.spec/design/domain-model.md`, `.spec/design/data-model.md`, `.spec/design/data-storage.md`,
`.spec/design/architecture.md`, `.spec/design/observability.md`, `.spec/discovery/vision.md`, `.spec/discovery/scope.md`

## 観点別サマリー（review-registry.json 準拠、5観点）

| 観点 | スコア(1-5) | 主な指摘 |
|---|---|---|
| consistency | 4.0 | ドメインモデル・ER図・アーキテクチャ図の対応は一致。用語のブレなし |
| data-integrity | 4.0 | ER図・トランザクション境界・SQLite選定の根拠は明記済み。マイグレーション計画は初期版のみで将来拡張が粗い（minor） |
| operations | 3.0 | 可観測性は軽量記述のみ。障害復旧は手動運用前提で個人用途としては妥当だが、バックアップ手順の具体化が未記載（major） |
| risk | 3.5 | フレームワーク未選定（architecture.md のギャップ節）が実装フェーズのリスク。要件化されるまでは許容範囲（major） |
| business | 4.0 | scope.md の MoSCoW と設計成果物の対応は一致。Non-Goal の逸脱なし |

## 指摘事項

| ID | severity | 内容 | 対象 |
|---|---|---|---|
| OPS-001 | major | バックアップ・復旧手順が「手動」としか記載されておらず具体的な頻度・手順がない | observability.md |
| RSK-001 | major | Controller/View層の技術スタック（フレームワーク）が未確定 | architecture.md |
| DIN-001 | minor | マイグレーション計画が初回スキーマ作成のみで、将来のロールバック手順が未記載 | data-storage.md |

## 統合判定

**判定: CONDITIONAL_PASS**

- 加重平均スコア: 約 3.7（quality_gates の PASS 閾値 3.5 は超えるが、`all_perspectives_min: 3.0` を operations がぎりぎり満たす一方、major 指摘が2件存在するため CONDITIONAL_PASS が実態に即した判定）
- Critical指摘: 0件（PASS/CONDITIONAL_PASS のいずれの上限も満たす）
- Major指摘: 2件（CONDITIONAL_PASS の上限8件以内）

## 条件（Design Gate 通過のために消化すべき事項）

1. フレームワーク選定を要件として明確化する（RSK-001）
2. バックアップ手順を具体化する、または個人用途のNon-Goalとして明示的に記録する（OPS-001）

上記2条件を消化した上で、人間による Design Gate 裁定を依頼する。
