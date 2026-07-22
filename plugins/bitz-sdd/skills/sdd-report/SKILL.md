---
name: sdd-report
description: BitzSDD — .spec/（仕様・設計・検証のマスター）から人間向けの開発進捗・品質レポート（.spec/reports/status-report.md）を自動生成するスキル。ユーザーが「進捗を教えて」「レポートを出力して」「status-report」「報告書」「検証状況」に言及したとき、または sdd-core のマイルストーン完了時に使用する。
metadata:
  version: "0.4.1"
  author: br7.hide
  created: "2026-07-09"
  updated: "2026-07-22"
---

# sdd-report

BitzSDD の仕様・検証マスターである `.spec/` ディレクトリから、開発の進捗状況、要件の検証状況、設計レビュー結果などを集計した統合レポート（`.spec/reports/status-report.md`）を生成します。

> **`spec_status.py` との使い分け**: 本スキル（`sdd_report.py`）は人間向けの**詳細レポートを
> `.spec/reports/` に生成**する（ファイル出力あり）。一方、フェーズ・status 件数・次アクションの
> **軽量な即時照会**（標準出力のみ・ファイル生成なし）は sdd-core の `spec_status.py` を使う。
> 両者は重複実装しない。「レポート成果物が欲しい」→ `sdd_report.py`、
> 「いま何件どの status か今すぐ知りたい」→ `spec_status.py`。
>
> **`sdd-plan` との責務境界**: 本スキルは人間向け成果文書の生成（`.spec/reports/` に書く）を担う。
> セッション内の対話ナビゲーション（フェーズ判定・次アクション提案。原則ファイルを書かない）は
> `sdd-plan` が担当する。「次に何をすべきか」と聞かれたら本スキルではなく `sdd-plan` に切り替える。

## 1. 責務
1.  `.spec/` ディレクトリ内の全成果物の状態を走査。
2.  以下のメトリクスとステータスを自動集計：
    *   **ディスカバリー状況**: 仮説検証ゲートの合否 (`assumptions.md` の判定)
    *   **要件ライフサイクル**: 登録されている要件の数と、それぞれのステータス分布 (`draft`, `approved`, `implementing`, `verified`, `promoted`)
    *   **設計状況**: `domain-model`, `api-design`, `architecture` の有無と最終更新
    *   **レビュー状況**: `.spec/reviews/` の判定結果 (`PASS`, `CONDITIONAL_PASS`, `FAIL`)
    *   **タスク進行状況**: `.spec/tasks/` にあるタスクの進捗 (`todo`, `doing`, `done`)
3.  集計結果を `.spec/reports/status-report.md`（人間向けマークダウン）に出力。

## 2. 実行手順
1.  **データスキャンと生成**:
    *   リポジトリルートで `python3 <このスキル>/scripts/sdd_report.py <repo-root>` を実行。
    *   スクリプトは `.spec/reports/status-report.md` を作成または更新する。
2.  **結果の提示**:
    *   生成された `.spec/reports/status-report.md` へのリンクを示し、重要なサマリー（警告やFAILなど）を人間に報告する。

## 3. レポート構成案 (.spec/reports/status-report.md)
*   **ダッシュボード (要約)**: 総合ステータス（Green/Yellow/Red）、要件進捗率
*   **仕様詳細**: Discovery / Design の確立状況
*   **要件ステータス一覧**: ライフサイクル別（Approved/Implementing/Verified）のカウント
*   **検証・レビュー結果**: 最新のレビュー報告（PASS/FAIL）および未解消の課題
*   **タスク進捗**: 未完了/完了タスクの割合と一覧
