---
id: FLW-DSC-002
title: "bitz-flow 成功指標（North Star Metric + 入力指標 + ガードレール）"
status: draft
version: 1.0
updated: 2026-07-18
owner: hide
---

# 成功指標（North Star Metric + 入力指標 + ガードレール）

> 切り出し discovery。OSS / 個人開発のため計測基盤は未整備。目標値の大半は `TBD`。
> ビジョン（FLW-DSC-001）の「勝利の定義」を測定可能な形にし、スコープ（FLW-DSC-003）の錨とする。

## North Star Metric（NSM）— 1つだけ

**「bitz-flow の規約に従って完了した開発サイクル（フロー選択 → 実装 → コミット規約準拠 →
squash merge / worktree 破棄）の数」**（= 規約どおりに land または安全に復元されたタスク／Issue の数）。

- 収益に先行しない（OSS なので収益は指標外）が、**「規約が実運用で回った」= 中核価値が届いた**を捉える先行指標。
- 顧客が受け取った価値を顧客の言葉で測る: 「スキルを起動したこと」ではなく「フローが最後まで規約どおり回ったこと」。
- バニティ指標（インストール数・スキル起動回数）を NSM にしない。

## 入力指標（3〜5個）

分解レンズ: **広さ × 深さ × 頻度 × 効率**。

| # | 入力指標 | 定義 | 目標値 |
|---|---|---|---|
| I1（広さ） | bitz-flow を1回以上使ったプロジェクト数 | フロー規約に従った履歴を持つリポジトリ数 | `TBD`（現状: 作者の 1 系統） |
| I2（深さ） | 1サイクルあたり並列投入した worktree 数 | flow-worktree で同時運用したブランチ数 | `TBD` |
| I3（頻度） | Conventional Commits + Implements フッター準拠率 | 規約準拠コミット ÷ 全コミット | `TBD`（併用時は spec_inspect で突合可能） |
| I4（効率） | 失敗時の worktree 破棄→再投入で復元できた率 | 破棄再投入で回復した失敗 ÷ 全失敗（`reset --hard` 不使用の証跡） | `TBD` |

## マッピング枠組み（HEART を採用）

開発体験中心のツールのため **HEART**（Adoption / Retention / Task success）を採用:
- Adoption: 新規プロジェクトで最初の並列開発／PR フローに bitz-flow が使われた率。
- Retention: 同一利用者が複数プロジェクト／複数サイクルで再利用した率。
- Task success: フロー選択 → 実装 → マージバック（or 破棄復元）が規約どおり破綻なく完走した率。

## ガードレール指標（NSM 最適化で劣化させない対抗指標）

- **G1: ガードレール非違反率** — 失敗時復元で `git reset --hard` / `git push --force` /
  `git worktree remove` 以外の破壊的操作を使わないこと。目標: 違反0（AGENTS.md ガードレールが正）。
- **G2: スキルの自己完結性** — 他スキルの references を相対参照しない（AGENTS.md 規約）。目標: 違反0。
- **G3: SDD 連携の非侵食** — bitz-flow は `.spec/` の仕様・タスクの**正を持たない**。Implements フッターや
  `.spec/tasks` 連携の規定の正は bitz-sdd 側に残す。bitz-flow は接続点（併用節）だけを持つ。目標: 二重規定0。

## 下流への接続

- G1/G2/G3 は Design Gate 後に NFR（verification_method: 静的検査 / レビュー）へ派生する第一候補。
- 計測基盤（テレメトリ）は現状なし。指標収集の仕組み自体が未実装のため、当面は作者の手集計 `[proto / 未検証]`。
