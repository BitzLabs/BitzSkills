---
id: DDD-DSC-002
title: "bitz-ddd 成功指標（North Star Metric + 入力指標 + ガードレール）"
status: draft
version: 1.0
updated: 2026-07-12
owner: hide
---

# 成功指標（North Star Metric + 入力指標 + ガードレール）

> 遡及 discovery。OSS / 個人開発のため計測基盤は未整備。目標値の大半は `TBD`。
> ビジョン（DDD-DSC-001）の「勝利の定義」を測定可能な形にし、スコープ（DDD-DSC-003）の錨とする。

## North Star Metric（NSM）— 1つだけ

**「bitz-ddd の3スキルによって生成され、後続の SDD 工程（要件派生・実装・検証）に実際に消費された
ドメイン設計成果物の数」**（= `.spec/design/stories/` ・ `domain-model.md` ・ `evaluation/scorecard.md` のうち、
下流の要件/タスクから参照されたもの）。

- 収益に先行しない（OSS なので収益は指標外）が、**「作った設計が下流に使われた」= 中核価値が届いた**を捉える先行指標。
- 顧客が受け取った価値を顧客の言葉で測る: 「DDD 成果物を作ったこと」ではなく「それが実装/検証に使われたこと」。
- バニティ指標（インストール数・スキル起動回数）を NSM にしない。

## 入力指標（3〜5個）

分解レンズ: **広さ × 深さ × 頻度 × 効率**。

| # | 入力指標 | 定義 | 目標値 |
|---|---|---|---|
| I1（広さ） | DDD スキルを1回以上起動した SDD プロジェクト数 | `.spec/design/` に ddd-* 成果物を持つワークスペース数 | `TBD`（現状: 作者の 1 系統） |
| I2（深さ） | 1プロジェクトあたりの DDD 成果物点数 | story + domain-model + scorecard の合計 | `TBD` |
| I3（頻度） | ddd-story → ddd-model の一連完走率 | ストーリー作成後にモデル化まで到達した割合 | `TBD` |
| I4（効率） | 2パス導出で Pass 2 が拾った暗黙概念の割合 | ddd-model の暗黙概念数 ÷ 全モデル要素数（設計の質の代理指標） | `TBD` |

## マッピング枠組み（HEART を採用）

UX/設計体験中心のツールのため **HEART**（Adoption / Retention / Task success）を採用:
- Adoption: 新規 SDD プロジェクトで DDD スキルが最初に呼ばれた率。
- Retention: 同一利用者が複数プロジェクトで再利用した率。
- Task success: ドメインストーリー → モデル → 要件派生（1 Activity ≒ 1 EARS 節）が破綻なく繋がった率。

## ガードレール指標（NSM 最適化で劣化させない対抗指標）

- **G1: bitz-sdd 契約準拠率** — 生成成果物が sdd-core の artifact-frontmatter / DSN- 体系に 100% 準拠すること。
  DDD 成果物を増やすために契約を破らない。目標: 100%（`release_check.py` / `spec_inspect.py` で機械検証可能）。
- **G2: スキルの自己完結性** — 他スキルの references を相対参照しない（AGENTS.md 規約）。目標: 違反0。
- **G3: 導出の根拠づけ率** — 根拠のないモデル要素・ストーリーステップを捏造しない。
  Pass 2 追加要素の根拠記録率 目標 100%。

## 下流への接続

- G1/G3 は Design Gate 後に NFR（verification_method: 静的検査）へ派生する第一候補。
- 計測基盤（テレメトリ）は現状なし。指標収集の仕組み自体が未実装のため、当面は作者の手集計 `[proto / 未検証]`。
