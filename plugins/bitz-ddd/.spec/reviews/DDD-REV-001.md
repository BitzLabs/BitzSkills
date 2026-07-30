---
id: DDD-REV-001
title: "bitz-ddd 設計レビュー統合レポート（requirements + discovery）"
status: active
version: 1.0
updated: 2026-07-22
owner: hide
decision: CONDITIONAL_PASS
---

# bitz-ddd 設計レビュー統合レポート

- **review_id**: 2026-07-22-DDD-01
- **対象**: `plugins/bitz-ddd/.spec/requirements/*.md`（DDD-FR-001, DDD-FR-002）、
  `plugins/bitz-ddd/.spec/discovery/*.md`（DDD-DSC-001〜006）。
  `.spec/design/` は0件のため対象外。
- **判定**: **CONDITIONAL_PASS**
- **集計スコア**: 3.81（PASS ≥ 3.5 / CONDITIONAL ≥ 2.5）
  - PASS 不採用の理由: business 観点が 2.70 で `all_perspectives_min: 3.0` を満たさない
    （CONDITIONAL_PASS の `min_perspective_floor: 2.0` は満たす）。

## 観点別スコア

| 観点 | スコア | 重み（正規化後） | 主要所見 |
|---|---|---|---|
| consistency | 3.95 | 0.20 | 用語は一貫。中核3スキルの要件トレースが皆無（major） |
| data-integrity | 対象外 | — | 永続データストアを扱わないため条件不成立 |
| operations | 3.90 | 0.267 | 読み取り専用制約が明確でセキュリティ良好。監視/DRはinfo指摘のみ |
| risk | 4.33 | 0.333 | 単一プロセスのため次元1・3はN/A。値不変条件の検証がminor |
| business | 2.70 | 0.20 | PoD差別化とNSM/入力指標がいずれも要件・計測に未接続（major×2） |

findings: 統合前 8 件 → 重複排除後 7 件（P0: 0 / P1: 1 / P2: 1 / P3: 5）

## P0 — Blocker

なし。

## P1 — Must Fix

- **SYN-001** [RVC-201, BIZ-101] 中核差別化3スキル（ddd-story/ddd-model/ddd-evaluate）にFR/NFR要件が皆無
  - 場所: `plugins/bitz-ddd/.spec/requirements/`（2件のみ）/ `plugins/bitz-ddd/.spec/discovery/scope.md:35-38`（Must帯）/ `plugins/bitz-ddd/.spec/discovery/positioning.md:29-37`（PoD D1-D3）
  - 問題: プラグインの存在意義であるMust機能（2パス導出必須のドメインモデリング、DDD12基準+MMI採点）にEARS要件が1件も無く、ビジネス上の差別化主張を検証可能な要件として辿れない。
  - 是正: 中核3スキルの主要挙動を遡及的にEARS要件として起票し、DDD-名前空間でトレース可能にする。

## P2 — Should Fix

- **SYN-002** [BIZ-201] North Star Metric・入力指標(I1-I4)が全てTBDで計測基盤が存在しない
  - 場所: `plugins/bitz-ddd/.spec/discovery/metrics.md:15-49`
  - 問題: NSM定義は明確だが目標値が軒並みTBDで、計測基盤なし（手集計 [proto/未検証]）。ガードレールG3（根拠づけ率）も未実装。
  - 是正: 少なくともG3の機械検証手段の目処をspec-issueとして検討する。

## P3 — Consider

- **SYN-003** [RVC-101] Discovery Gate裁定済み（assumptions.md 56-62行）なのに discovery 6件のfrontmatter statusがdraftのまま
- **SYN-004** [RVC-202] `.spec/design/` が0件のまま要件がverifiedに到達（現状は是正不要、規模拡大時の運用ルール明文化を推奨）
- **SYN-005** [OPS-101] ddd-doctorの診断結果が傾向計測に残らない（任意）
- **SYN-006** [OPS-201] git以外の明示的バックアップ戦略の記述がない（是正不要、将来の明記のみ推奨）
- **SYN-007** [RSK-201] DDD-FR-002の「値不変」不変条件の検証が目視確認のみ（機械diffスクリプト化を推奨）

## CONDITIONAL_PASS の通過条件

- [ ] SYN-001（P1）: 中核3スキルの遡及要件化に着手する、または着手時期の方針を人間が裁定する
- [ ] SYN-002（P2）: NSM/入力指標の計測方針（少なくともG3）を人間が裁定する

## 人間への裁定依頼

この判定は推奨です。Design Gate / Promotion Gate の裁定（proposed→active 化・通過）は上記を確認のうえ行ってください。
特に SYN-001 は起票のみ推奨であり、本レビューでは spec-issue の起票は行っていません。
