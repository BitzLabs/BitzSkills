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
| `bitz-sdd` | SDDワークフローの常時運用。要件ライフサイクル（draft→approved→implementing→verified→promoted）、EARS検証、失敗プロトコル、並列実行、Promotion Gate。spec_inspect.py（.planning/ 側の構造検証・影響分析）同梱 |
| `sdd-docs` | docs/（人間ナラティブ層）の初期化と検証。docs/ ツリーのテンプレート一式と docs_inspect.py（docs/ 側の構造検証）同梱。プロジェクトごとに最初に1回使う |

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
2. 以降の設計・実装・検証はすべて `bitz-sdd` の規律で進行
3. feature 完了時は Promotion Gate（人間承認）で docs/ へ知見を還流
