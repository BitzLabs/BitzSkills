---
name: sdd-core
description: BitzSDD — 仕様駆動開発（SDD）ワークフローを運用するメインスキル。要件定義・仕様作成・実装・検証・完了処理のすべてをこの規律に従って実行する。ユーザーが「仕様駆動」「SDD」「要件」「EARS」「spec」「タスク分解」「feature実装」に言及したとき、リポジトリに .spec/ や AGENTS.md が存在するとき、または新機能の設計・実装・検証・リリース処理を依頼されたときは、明示的な指示がなくても必ずこのスキルを使うこと。要件の変更・廃止・番号管理・テスト失敗時の対応・ドキュメント更新もすべて本スキルの管轄。
metadata:
  version: "1.5.0"
  author: br7.hide
  created: "2026-07-07"
  updated: "2026-07-11"
---

# BitzSDD Workflow (spec駆動開発)

個人用の仕様駆動開発フレームワーク。`.spec/`（仕様・設計・検証のマスター）を中心とし、`docs/`（人間ナラティブ層）との双方向同期を維持しながら、EARS記法の要件を機械検証で充足させます。

## 憲法（5原則）

1.  **spec-centered** — `.spec/` が開発の真実の源 (SSOT) であり、仕様・設計・検証はすべてここに集約される。
2.  **双方向同期 (docs ⇄ .spec)** — `docs/` と `.spec/` は `sdd_sync.py` によって双方向に同期され、手動修正の逆反映が可能。
3.  **検証中心** — 人間は行をレビューしない。要件やテストの合否は機械（`spec_inspect.py`）が排出し、人間はゲートと例外だけを見る。
4.  **権限分離** — エージェントは契約を実装できるが、書き換えられない。仕様の変更権は常に人間が持つ。
5.  **短命と永続の分離** — 要件仕様はライフサイクルによって管理され、docs/ および LESSONS_LEARNED は永続。

## ディレクトリ構成

```text
docs/                        永続・人間ナラティブ（.spec から自動生成 / 逆同期対象）
  MASTER.md / 01-context/ / 02-design/(ARCHITECTURE, DECISIONS) / 06-reference/ / 08-knowledge/LESSONS_LEARNED.md
.spec/                       仕様・設計・検証のマスター
  PROJECT.md / ROADMAP.md
  discovery/                 上流探索成果物 (DSC-*.md)
  requirements/              1要件1ファイル。FR-*.md NFR-*.md CON-*.md
  design/                    設計成果物 (DSN-*.md, INF-*.md)
    stories/                 ドメインストーリー個別ファイル
  reviews/                   多観点レビュー結果 (REV-*.md など)
  spec-issues/SI-*.md        エージェント発の仕様変更提案
  specs/<feature>/           EARS→検証マッピング、boundary×checks×depends_on
  tasks/                     タスク分解+依存グラフ
  STATE.md                   ブランチローカルの生きたメモリ
  metrics.md                 ワークフロー計測
  reports/                   進捗・ヘルスレポート (sdd-report により自動生成)
    status-report.md         統合進捗状況レポート
AGENTS.md                    読み込みプロトコル+権限マトリクス
```

## フェーズ・ルーティング

今どのフェーズかを判定し、対応するスキルまたは reference を読んでから作業します：

| いまやること | フェーズ | 連携スキル |
|---|---|---|
| プロジェクト把握・docs/整備・同期 | Map / Discuss | `sdd-docs` (初期化・検証・双方向同期) |
| ビジョン・成功指標・スコープ・仮説検証 | Map / Discuss | `sdd-discovery` (.spec/discovery/ 作成) |
| ドメイン・API・アーキテクチャ設計 | Discuss | `sdd-design` (.spec/design/ 作成。DDD 手法は bitz-ddd の `ddd-story`/`ddd-model` が任意で提供) |
| データ格納設計（永続データを扱う場合のみ） | Discuss | `sdd-data` (.spec/design/data-model.md ほか作成) |
| インフラ・セキュリティ・SLO・DR・コスト設計 | Discuss | `sdd-ops` (.spec/design/ 作成) |
| 設計ドキュメント・仕様の多観点レビュー | Discuss / Gate前 | `sdd-review` (.spec/reviews/ 作成) |
| 要件起票・採番・変更・廃止 | Plan | `sdd-core` (requirements/ 更新) |
| 進捗・検証・レビュー状況のレポート作成 | 報告 | `sdd-report` (.spec/reports/ 作成) |
| 仕様→タスク分解・並列投入 | Plan / Execute | `sdd-implement` (.spec/tasks/ 分解。implements / depends_on / boundary 宣言) |
| 実装（要件 ID 紐づけ・契約保護） | Execute | `sdd-implement` (implementation-discipline) |
| テスト仕様の導出・テスト作成 | Execute / Verify | `sdd-test` (EARS→テスト導出、.spec/specs/ 記録) |
| 検証 red・エラー・矛盾発見 | Execute / Verify | `sdd-core` (failure-protocol.md) |
| 検証・カバレッジ確認 | Verify | `sdd-test` + `sdd-core` (spec_inspect.py 実行) |
| feature完了・docs/同期・昇格 | Promotion Gate | `sdd-core` / `sdd-docs` (push/pull) |

## モノリポ運用とクロスリファレンス (Monorepo & Workspaces)

複数のプラグインやサービスを1つのリポジトリで管理する場合、以下のベストプラクティスに従います：

1. **分散配置**: 各パッケージディレクトリの直下に `.spec/` と `docs/` を配置し、独立した BitzSDD プロジェクトとして扱います。
2. **名前空間の分離**: グローバルなID衝突を避けるため、プロジェクト固有のプレフィックスを使用します（例: `PLG-FR-001`）。
3. **クロスリファレンス**: プラグイン間で要件を参照することが可能です。検証ツールに `--workspace <dir>` を渡すことで、グローバルな名前空間として参照が解決されます。
4. **ルートとプラグインの混在 (Root Workspace)**: リポジトリのルートにも `.spec/` が存在する場合（全プラグイン共通のグローバル要件やアーキテクチャ定義など）、ルートディレクトリ自体も1つのワークスペースとして扱います。ツールには `--workspace . plugins/*` のように複数指定可能とし、プラグインからルートの要件（例: `CORE-NFR-001`）をクロスリファレンスできるようにします。
5. **一括検証**: `python scripts/spec_inspect.py --workspace . plugins/*/` を実行することで、ルートと全プロジェクトを一括で検証できます。

## 検証ツール

構造検証・孤児/幽霊検出・カバレッジ・変更影響分析は同梱スクリプトで実行します:

```bash
python3 scripts/spec_inspect.py <repo-root>              # 全検証 → inspection-report.md
python3 scripts/spec_inspect.py --workspace . plugins/*  # モノリポ一括検証（クロスリファレンス解決）
python3 scripts/spec_inspect.py <repo-root> --impact FR-012   # FR-012変更の影響成果物を列挙
```
