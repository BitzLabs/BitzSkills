---
id: SKC-DSC-002
title: "skill-creator 成功指標（North Star Metric + 入力指標 + ガードレール）"
status: draft
version: 1.0
updated: 2026-07-12
owner: hide
---

# 成功指標（North Star Metric + 入力指標 + ガードレール）

> ビジョン（vision.md, SKC-DSC-001）の「勝利の定義」を測定可能な形にする。
> 遡及 discovery のため、目標値は未計測のものが多く `TBD` と明示する。発明しない。

## North Star Metric（NSM）— 1つだけ

**「検証をパスして実環境に配置され、稼働し続けているスキルの数（検証済み稼働スキル数）」**

- 顧客が受け取る中核価値は「作っただけ」ではなく「仕様検証を通り、効果測定を経て、
  実際に配置され使われ続けるスキル」であるため、そこを 1 指標で捉える。
- 収益に先行する遅行でない指標（本プロダクトは非商用のため、価値の代理は
  「使える成果物の蓄積」）。
- チームがプロダクトの仕事で動かせる（各スキルが NSM を押し上げるレバーを持つ）。
- アンチパターンを避ける: 「生成した SKILL.md 数」「pipeline 起動回数」は
  バニティ指標なので NSM にしない。

現在値: `TBD`（計測基盤なし。当面は本モノレポ内の配置済みスキル本数を手動概算）。

## 入力指標（3〜5個）— 広さ × 深さ × 頻度 × 効率

| # | 入力指標 | 対応レバー（担当スキル） | 定義 | 測定方法・ソース | 目標値 |
|---|---|---|---|---|---|
| I1 | 仕様検証パス率 | skill-validator | validator チェックリストで PASS したスキルの割合 | validator 実行結果 | `TBD`（暫定目標 100%） |
| I2 | 効果測定実施率 | skill-tester / skill-evaluator | 配置スキルのうち あり/なし比較レポートを持つ割合 | `evals/<skill>/report.md` の有無 | `TBD` |
| I3 | 初回作成→配置のリードタイム | skill-creator → skill-packager | 作成着手から実環境配置までの所要 | 手動記録 | `TBD` |
| I4 | 自己改善ループ被覆率 | skill-instrumenter / observer | 計装済み（自己観察を持つ）スキルの割合 | SKILL.md 内の observer ステップ有無 | `TBD` |
| I5 | 観察→改善の消化率 | skill-improver | observations.jsonl の open 観察から起票・裁定された割合 | `.spec/spec-issues/` と observations.jsonl の突合 | `TBD` |

（4〜5 個に収める。I1・I2 が中核レバー、I4・I5 が配置後の継続改善レバー。）

## マッピング枠組み — HEART を採用

UX 中心の開発ツールのため AARRR より HEART が合う。

- **Task success（中核）**: I1 仕様検証パス率・I3 リードタイム。
- **Adoption**: NSM 検証済み稼働スキル数。
- **Retention**: I4 自己改善ループ被覆率（配置後も面倒を見続けられているか）。
- **Engagement / Happiness**: `TBD`（開発者体験の定性指標は未収集）。

## ガードレール指標（NSM 最適化中に劣化させない対抗指標）

- **G-回帰なし**: 検証済み稼働スキルを増やす過程で、既存スキルの validator PASS を
  壊さない（version bump 忘れ・frontmatter 欠落を出さない）。ソース: `release_check.py`。
- **G-薄さ維持**: スキル本数を増やしても SKILL.md 本文が肥大しない
  （progressive disclosure を守り references/ へ逃がす）。ソース: skill-optimizer の観点。
- **G-自己完結**: スキルを量産しても、他スキルの references を相対参照する
  結合を生まない（フォルダ単位コピーを壊さない）。ソース: validator チェックリスト。

## 下流への接続

ガードレール（release_check PASS 維持・自己完結）は Design Gate 後に
NFR（verification_method: benchmark 等）へ派生する第一候補。数値目標が確定した時点で
検証可能な形（母集団・期間を明示）に落とす。現時点は多くが `TBD`。
