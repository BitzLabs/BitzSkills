---
name: quality-init
description: bitz-quality の品質管理・QA環境（.spec/quality/ 配下の各ディレクトリおよび再発防止ルール台帳）を対象プロジェクトへ初期化・展開する。「品質環境を初期化して」「quality-init」「QA環境をセットアップして」「.spec/quality を作って」と言われたとき、または bitz-quality 導入直後の初期設定時に使用する。初期化後の環境診断は quality-doctor、QAプロセスの統括は quality-core が担当する。
metadata:
  version: "0.1.0"
  author: br7.hide
  created: "2026-08-14"
  updated: "2026-08-14"
---

# quality-init

`quality-init` は、対象プロジェクトに `bitz-quality` の品質管理・QAワークスペース構造を展開する初期化スキルです。

## 1. 目的と責務

- **ディレクトリ構造の確立**: `.spec/quality/` 配下にセッション、スコアリング、分析、観点、レポート、ルールの各格納領域を作成する。
- **再発防止ルール台帳の配備**: レビュー・不具合分析で得られた `general_rule` を蓄積する `rules-ledger.md` を初期化する。
- **安全な初期化**: 既存のファイルやディレクトリを破壊・上書きせず、差分のみを安全に追加する。

## 2. 展開されるディレクトリ構造

```text
.spec/quality/
├── sessions/      # qa-session.json（オーケストレーション進捗）
├── scorings/      # 5軸リスク評価 & 関与レベル判定結果
├── analyses/      # 影響分析・不具合傾向分析レポート
├── viewpoints/    # テスト観点一覧設計書
├── reports/       # quality-summary.md（リリース判定サマリー）
└── rules/         # rules-ledger.md（再発防止ルール台帳）
```

## 3. 実行手順

同梱スクリプト `<このスキル>/scripts/quality_init.py` を実行して初期化します。

```bash
# カレントディレクトリの初期化（事前確認）
python3 <このスキル>/scripts/quality_init.py --dry-run

# カレントディレクトリの初期化実行
python3 <このスキル>/scripts/quality_init.py .
```

## 4. 規律と禁止事項

- **無断上書きの禁止**: 既存の `.spec/quality/` 配下の成果物を勝手に消去・上書きしない。
- **リポジトリ外書き込みの禁止**: プロジェクトディレクトリ外部への書き込みを行わない。
- **診断との連携**: 初期化後は `quality-doctor` を呼び出して環境の健全性を検証する。
