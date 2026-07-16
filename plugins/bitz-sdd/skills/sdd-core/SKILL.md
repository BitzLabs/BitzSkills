---
name: sdd-core
description: BitzSDD — 仕様駆動開発（SDD）ワークフローを運用するメインスキル。要件定義・仕様作成・実装・検証・完了処理のすべてをこの規律に従って実行する。ユーザーが「仕様駆動」「SDD」「要件」「EARS」「spec」「タスク分解」「feature実装」に言及したとき、リポジトリに .spec/ や AGENTS.md が存在するとき、または新機能の設計・実装・検証・リリース処理を依頼されたときは、明示的な指示がなくても必ずこのスキルを使うこと。要件の変更・廃止・番号管理・テスト失敗時の対応・ドキュメント更新もすべて本スキルの管轄。
metadata:
  version: "1.12.0"
  author: br7.hide
  created: "2026-07-07"
  updated: "2026-07-16"
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
| 現状把握・次アクション提案 | 全フェーズ | `sdd-plan` (spec_status.py の実行と解釈。対話ナビゲーション) |
| 要望のインテーク・spec-issue 起票 | 全フェーズ | `sdd-issue` (整理→重複チェック→予備判定→起票→裁定材料提示) |
| プロジェクト把握・docs/整備・同期 | Map / Discuss | `sdd-docs` (初期化・検証・双方向同期) |
| ビジョン・成功指標・スコープ・仮説検証 | Map / Discuss | `sdd-discovery` (.spec/discovery/ 作成) |
| ドメイン・API・アーキテクチャ設計 | Discuss | `sdd-design` (.spec/design/ 作成。DDD 手法は bitz-ddd の `ddd-story`/`ddd-model` が任意で提供) |
| データ格納設計（永続データを扱う場合のみ） | Discuss | `sdd-data` (.spec/design/data-model.md ほか作成) |
| インフラ・セキュリティ・SLO・DR・コスト設計 | Discuss | `sdd-ops` (.spec/design/ 作成) |
| 設計ドキュメント・仕様の多観点レビュー | Discuss / Gate前 | `sdd-review` (.spec/reviews/ 作成) |
| 要件起票・採番・変更・廃止 | Plan | `sdd-core` (requirements/ 更新) |
| 進捗・検証・レビュー状況のレポート作成 | 報告 | `sdd-report` (.spec/reports/ 作成) |
| 仕様→タスク分解・並列投入 | Plan / Execute | `sdd-implement` (.spec/tasks/ 分解。implements / depends_on / boundary 宣言) |
| ブランチ・worktree・PR の Git 運用 | Execute | `sdd-git` (フロー選択 / worktree 並列 / Issue 駆動。parallel-git.md を拡張) |
| 実装（要件 ID 紐づけ・契約保護） | Execute | `sdd-implement` (implementation-discipline。着手前に委譲ゲート＝delegation-routing.md で委譲判定) |
| 委譲・相談・合議の判断（実装移行時） | Execute | `sdd-implement` の委譲ゲート ＋ `env-orchestration` (委譲型/相談型/合議型の決定木。導入時) |
| テスト仕様の導出・テスト作成 | Execute / Verify | `sdd-test` (EARS→テスト導出、.spec/specs/ 記録) |
| 検証 red・エラー・矛盾発見 | Execute / Verify | `sdd-core` (failure-protocol.md) |
| 検証・カバレッジ確認 | Verify | `sdd-test` + `sdd-core` (spec_inspect.py 実行) |
| feature完了・docs/同期・昇格 | Promotion Gate | `sdd-core` / `sdd-docs` (push/pull) |

## 軽量レーン（小さな変更のためのショートカット）

小さな修正（1スキルの軽微な変更・記載漏れの修正・文言調整など）は、フルワークフローの
オーバーヘッドを避けるため **spec-issue → 要件（draft → approved は人間）→ タスク** だけで回してよい:

1. `.spec/spec-issues/` に起票（変更の必要性と影響範囲）— 採番・雛形は `spec_scaffold.py` を使う。
   要望の整理・重複チェック・可否の予備判定を含むインテーク運用フローは `sdd-issue` が定型化する
   （規律・ライフサイクルの正は本スキル sdd-core のまま。裁定は人間専用）
2. 要件化が必要なら `.spec/requirements/` に draft 起票（`spec_scaffold.py`）→ 人間が approved 化
   （`spec_update.py --by-human`）。既存要件の範囲内なら要件追加も不要
3. `sdd-implement` のタスク分解（1タスクで可、`spec_scaffold.py`）→ 実装 → `sdd-test` 検証

**discovery / design はスキップしてよい**。ただし契約（公開 API・`.spec` スキーマ・
frontmatter 書式）に触れる変更はショートカット禁止 — 通常フローと Design Gate を通すこと。

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

## 状況照会（軽量）

セッション冒頭に「いま何フェーズか・要件/spec-issue/タスクが何件どの status か・次に何をすべきか」を
`.spec/` を読み歩かずに1コマンドで得るには、読み取り専用の `spec_status.py` を使います
（**`.spec/` へは一切書き込まない**）:

```bash
python3 scripts/spec_status.py <repo-root>              # 人間向けテキストサマリ
python3 scripts/spec_status.py <repo-root> --json       # エージェント向け JSON
python3 scripts/spec_status.py --workspace . plugins/*  # 複数ワークスペースを一括照会
```

**`sdd_report.py` との使い分け**: `spec_status.py` は軽量な即時照会（標準出力のみ・ファイル生成なし）。
人間向けの詳細レポートを `.spec/reports/` に生成するのは `sdd-report` スキルの `sdd_report.py`。
両者は重複実装せず、照会は `spec_status.py`、レポート成果物は `sdd_report.py` に役割を分ける。
なお「いま何をすべきか」の**解釈と次アクション提案**（フェーズ判定・ゲート状態・着手可能タスクの提示）は
`sdd-plan` スキルに一本化されている — 本スクリプトはその機械集計層。

## 起票・status 遷移（定型処理）

採番・雛形生成と status 遷移は手書きせずスクリプトで行う。書式ブレ・採番衝突・権限逸脱を
構造的に防ぐ（`spec_scaffold.py` は spec_inspect PASS の雛形を、`spec_update.py` は
lifecycle.md の権限マトリクスをコードで強制する）:

```bash
# 採番付き雛形生成（要件 / spec-issue / task / 設計ノート DSN）
python3 scripts/spec_scaffold.py <workspace> requirement --prefix CORE-FR --domain tooling --title "..."
python3 scripts/spec_scaffold.py <workspace> spec-issue  --prefix SI-CORE --target "..."
python3 scripts/spec_scaffold.py <workspace> task --implements CORE-FR-004 --prefix CORE-TSK --boundary "..."
python3 scripts/spec_scaffold.py <workspace> design --prefix DSN --title "..." [--status draft] [--implements CORE-FR-006]

# 生成時に統制語彙を検証（verification_method / domain / status が語彙外なら非ゼロで失敗し雛形を
# 生成しない。語彙は spec_inspect と単一の正を共有。domains.md 不在時 domain 検証はスキップ。CORE-FR-010）

# status 遷移（権限マトリクス強制）
python3 scripts/spec_update.py <workspace> CORE-FR-004 --to implementing            # エージェント許容遷移
python3 scripts/spec_update.py <workspace> CORE-FR-004 --to approved --by-human      # 人間専用遷移は要フラグ
```

**権限の分離**: `draft→approved` / `open→accepted` / `verified→promoted` / `任意→deprecated` は
人間専用で、`--by-human` が無ければ拒否される。権限マトリクスに無い遷移は誰でも拒否。
遷移は対象の frontmatter を書き換え、`.spec/STATE.md` に記録を残す。詳細は
`references/lifecycle.md` の状態遷移表が正。
