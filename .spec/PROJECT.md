# BitzSkills ルートワークスペース（BitzLabs標準エージェント開発環境）

BitzSkills は、**BitzLabs でAIエージェントを用いて開発する際の標準作業環境**を、
Agent Skills 準拠のクロスプラットフォームなプラグインとして定義・検証・配布するモノレポ。

ルート `.spec/` は、標準環境全体のビジョン・スコープ・共通要件・検証状態のSSOTである。
モノレポ運用（sdd-core の Monorepo & Workspaces 節）に従い、
**ルート = 標準環境全体と全プラグイン共通の契約**、`plugins/*` = 各プラグイン固有のワークスペースとする。

## 標準環境の境界

- 対象: AIエージェント向けガードレール、Git運用、仕様・設計・実装・検証の規律、
  スキル／プラグイン開発、3プラットフォームへの配布・更新。
- 構成: 全プラグイン強制ではなく、用途別プロファイル（標準開発 / DDD / 軽量Git /
  スキル開発 / プラグイン開発）。正は `.spec/discovery/scope.md`。
- 非対象: OS、IDE本体、言語ランタイム、クラウド基盤、アプリ固有雛形、認証情報管理。
- ビジョンと成功指標: `.spec/discovery/vision.md` / `metrics.md`。

- ID プレフィックス: `CORE-`（例: `CORE-CON-001`）
- 検証（正規コマンド）: `python3 scripts/spec inspect --workspace . plugins/*`
  — このモノリポでは常にこの形を使う。ルート単体（末尾 `.`）は `tests/` が参照する他ワークスペースの
  ID（例: `tests/test_env_guard.py` の `ENV-*`）を解決できず幽霊参照で常時 FAIL するため（SI-CORE-023）。
  （CI の release_check / pytest が要件の実効的な検証手段）

## ブートストラップ対策（重要）

標準環境自身に適用する bitz-sdd は**リリース済み（main にマージ済み）バージョンに固定**し、
開発中の作業ツリー版のスキルを自分自身の開発プロセスには適用しない。
sdd-core の破壊が開発プロセスの破壊に直結する自己参照を避けるため。

## 軽量レーン

小さなスキル修正は spec-issue → 要件（draft → approved は人間）→ タスクのみで回し、
discovery / design はスキップしてよい（規定の正は sdd-core SKILL.md の軽量レーン節）。
