---
name: skill-pipeline
description: エージェントスキル開発の全工程（作成→検証→テスト→評価→最適化→配置）を統括し、状況に応じて適切な専門スキルへ案内するオーケストレーター。「スキルを作って公開まで面倒を見てほしい」「スキル開発の進め方が分からない」「スキルを一通り仕上げたい」と言われた場合や、どの工程から始めるべきか不明な場合に使用する。個別の作業は各専門スキル（skill-creator等）が行う。
metadata:
  version: "0.1.0"
  author: br7.hide
  created: "2026-07-05"
  updated: "2026-07-05"
---

# skill-pipeline

## 目的

スキル開発ライフサイクル全体を案内する。このスキル自身は作業を行わず、
各工程を担当する専門スキルへ委譲し、工程間の受け渡しと反復の判断だけを行う。

## 専門スキル一覧

| スキル | 責務 |
| --- | --- |
| `skill-creator` | ヒアリングと新規スキルの雛形作成 |
| `skill-validator` | 仕様準拠チェック（lint） |
| `skill-optimizer` | description最適化・本文分離・構造改善 |
| `skill-tester` | テストケース設計と実行（`evals/` へ保存） |
| `skill-evaluator` | 実行結果の採点と `report.md` 作成 |
| `skill-packager` | 実環境へのインストール・バージョンアップ・アンインストール・配布用zip化 |

## どこから始めるか（decision tree）

ユーザーの状況を確認し、入口を決める。

- **新しくスキルを作りたい** → `skill-creator` から標準フローを開始
- **既存スキルを良くしたい** → `skill-validator` で現状把握 → `skill-optimizer`
- **スキルの品質・効果を測りたい** → `skill-tester` → `skill-evaluator`
- **完成済みスキルを使える状態にしたい／更新・削除したい** → `skill-packager` のみ

## 標準フロー（新規作成の場合）

```
skill-creator（作成）
  → skill-validator（検証） … ❌/⚠️ があれば skill-optimizer で修正して再検証
  → skill-tester（テスト実行）
  → skill-evaluator（評価）
      → 不合格・改善提案あり:
          skill-optimizer（改善）→ skill-validator → skill-tester → skill-evaluator
          （合格するまで反復。3周しても改善しない場合は方針をユーザーと再検討）
      → 合格:
          skill-optimizer で description を最終調整（発動精度の仕上げ）
          → skill-packager（配置・配布）
```

## 進行のルール

- 各工程の開始時に「いまどの工程で、次に何をするか」を一言で伝える
- 工程をスキップしたい意向（「テストは要らない」等）があれば従い、スキップした
  事実だけ完了報告に残す
- 反復（改善→再テスト）に入るかどうかは、evaluatorのレポートを示した上で
  ユーザーに確認する
- 全工程完了時に、作成物のパス一覧・テスト結果サマリー・配置先をまとめて報告する
