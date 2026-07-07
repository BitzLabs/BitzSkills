# BitzSDD

個人用の仕様駆動開発（SDD）ワークフロー。docs/（人間の意図・永続）と
.planning/（AI実行契約・短命）を分離し、EARS記法の要件を機械検証で充足させる。
SDD運用仕様書 v1.0 を Claude Code / Antigravity 2.0 のスキルとして実装したもの。

## 5原則（憲法）

規則同士が衝突したら番号の小さい原則が勝つ。

1. **spec-anchored** — 仕様が実行を駆動するが、動くコードが最終的な真実
2. **一方向派生** — docs/ → .planning/ → code。逆流は Promotion Gate のみ
3. **検証中心** — 合否は機械が出し、人間はゲートと例外だけを見る
4. **権限分離** — エージェントは契約を実装できるが、書き換えられない
5. **短命と永続の分離** — .planning/ は feature 単位で使い捨て、docs/ は永続

## 収録スキル

| スキル | 責務 |
|---|---|
| `bitz-sdd` | SDDワークフローの常時運用。要件ライフサイクル（draft→approved→implementing→verified→promoted）、EARS検証、失敗プロトコル、並列実行、変更再伝播、3ゲート（Discovery/Design/Promotion）。spec_inspect.py（.planning/ 側の構造検証・影響分析・docs乖離検出）同梱 |
| `sdd-docs` | docs/（人間ナラティブ層）の初期化と検証。docs/ ツリーのテンプレート一式と docs_inspect.py（docs/ 側の構造検証）同梱。プロジェクトごとに最初に1回使う |
| `sdd-discovery` | 上流探索。ビジョン（Vision Board / PR-FAQ）→成功指標（NSM）→スコープ（MoSCoW / RICE）→ペルソナ・ジャーニー（JTBD）→ポジショニング→仮説検証ゲート（Go/No-Go）。成果物は docs/01-context/ の proposed ドラフト |
| `sdd-design` | 設計工程。ドメインストーリー→ドメインモデル（DDD）→API（3層）→アーキテクチャ（3ビュー+技術適合性）。既存コードには MMI / DDD 12基準評価。成果物は docs/02-design/ の proposed ドラフト |
| `sdd-review` | 設計ドキュメントの多観点並列レビュー（consistency / data-integrity / operations / risk / business）と統合判定（P0〜P3・PASS/CONDITIONAL_PASS/FAIL）。Design Gate / Promotion Gate への推奨を生成 |
| `sdd-infra` | インフラ・運用設計（インフラ構成 / セキュリティ / 可観測性・SLO / 災害復旧 / コスト見積もり）。設計ドキュメントまでが責務（IaC 生成はしない） |

## インストール

Claude Code:

```
/plugin marketplace add BitzLabs/BitzSkills
/plugin install bitz-sdd@bitzskills
```

Antigravity 2.0:

```
agy plugin install <このリポジトリ>/plugins/bitz-sdd
```

## 使い方の流れ

1. 新しいプロジェクトではまず `sdd-docs` で docs/ を初期化（最小6点、library は7点）
2. 「何を作るか」が未確立なら `sdd-discovery` で上流探索 → Discovery Gate（Go/No-Go）
3. `sdd-design`（必要なら `sdd-infra` も）で docs/ の設計層を proposed ドラフトとして確立
4. `sdd-review` の多観点レビュー判定を添えて Design Gate（人間が proposed → active 化）
5. 以降の要件派生・実装・検証はすべて `bitz-sdd` の規律で進行
6. feature 完了時は Promotion Gate（人間承認）で docs/ へ知見を還流

エージェントが docs/ に書けるのは `status: proposed` のドラフトのみ。proposed → active の
裁定は常に人間が行う（権限分離）。

## 帰属（Attribution）

`sdd-discovery` / `sdd-design` / `sdd-review` / `sdd-infra` の手法群、および `bitz-sdd` の
変更再伝播プロトコルは、[wfukatsu/nexus-architect](https://github.com/wfukatsu/nexus-architect)
（MIT License, Copyright (c) 2026 Wataru Fukatsu）の product / architect プラグインから、
ScalarDB・データベース移行等の DB 固有部分を除き、BitzSDD の憲法（proposed 機構・一方向派生・
権限分離）に合わせて翻案・圧縮したものです。

原ライセンス（MIT License）:

```
MIT License

Copyright (c) 2026 Wataru Fukatsu

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
