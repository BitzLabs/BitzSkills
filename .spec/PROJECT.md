# BitzSkills ルートワークスペース（ドッグフーディング）

BitzSkills リポジトリ自身のスキル・プラグイン開発を bitz-sdd（sdd-core）準拠で行うための
ルート `.spec/`。モノレポ運用（sdd-core の Monorepo & Workspaces 節）に従い、
**ルート = 全プラグイン共通のリポジトリ規約要件**、`plugins/*` = 将来の個別ワークスペースとする。

- ID プレフィックス: `CORE-`（例: `CORE-CON-001`）
- 検証: `python3 plugins/bitz-sdd/skills/sdd-core/scripts/spec_inspect.py .`
  （CI の release_check / pytest が要件の実効的な検証手段）

## ブートストラップ対策（重要）

自分に適用する bitz-sdd は**リリース済み（main にマージ済み）バージョンに固定**し、
開発中の作業ツリー版のスキルを自分自身の開発プロセスには適用しない。
sdd-core の破壊が開発プロセスの破壊に直結する自己参照を避けるため。

## 軽量レーン

小さなスキル修正は spec-issue → 要件（draft → approved は人間）→ タスクのみで回し、
discovery / design はスキップしてよい（規定の正は sdd-core SKILL.md の軽量レーン節）。
