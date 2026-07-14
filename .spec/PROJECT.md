# BitzSkills ルートワークスペース（ドッグフーディング）

BitzSkills リポジトリ自身のスキル・プラグイン開発を bitz-sdd（sdd-core）準拠で行うための
ルート `.spec/`。モノレポ運用（sdd-core の Monorepo & Workspaces 節）に従い、
**ルート = 全プラグイン共通のリポジトリ規約要件**、`plugins/*` = 将来の個別ワークスペースとする。

- ID プレフィックス: `CORE-`（例: `CORE-CON-001`）
- 検証（正規コマンド）: `python3 plugins/bitz-sdd/skills/sdd-core/scripts/spec_inspect.py --workspace . plugins/*`
  — このモノリポでは常にこの形を使う。ルート単体（末尾 `.`）は `tests/` が参照する他ワークスペースの
  ID（例: `tests/test_env_guard.py` の `ENV-*`）を解決できず幽霊参照で常時 FAIL するため（SI-CORE-023）。
  （CI の release_check / pytest が要件の実効的な検証手段）

## ブートストラップ対策（重要）

自分に適用する bitz-sdd は**リリース済み（main にマージ済み）バージョンに固定**し、
開発中の作業ツリー版のスキルを自分自身の開発プロセスには適用しない。
sdd-core の破壊が開発プロセスの破壊に直結する自己参照を避けるため。

## 軽量レーン

小さなスキル修正は spec-issue → 要件（draft → approved は人間）→ タスクのみで回し、
discovery / design はスキップしてよい（規定の正は sdd-core SKILL.md の軽量レーン節）。
