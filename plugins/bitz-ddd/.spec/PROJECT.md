# bitz-ddd ワークスペース

bitz-ddd プラグイン（DDD 設計手法: ddd-story / ddd-model / ddd-evaluate）自身の
SDD ワークスペース。モノレポ運用（sdd-core の Monorepo & Workspaces 節）に従う
個別ワークスペースであり、リポジトリ共通規約はルート `.spec/`（CORE-）が持つ。

- ID プレフィックス: `DDD-`（例: `DDD-FR-001`）
- 検証: `python3 plugins/bitz-sdd/skills/sdd-core/scripts/spec_inspect.py plugins/bitz-ddd`
  （クロスリファレンス解決は `--workspace . plugins/*`）

## 経緯（ブラウンフィールド開始）

本ワークスペースは SI-CORE-004（2026-07-12）により新設。プラグインは実装・リリース済みで、
仕様はまだ逆起票されていない（sdd-discovery の実施は SI-CORE-005 が扱う）。
以後の bitz-ddd 変更はすべて DDD- 名前空間で起票し、通常の SDD フロー
（要件 → タスク → 実装 → 検証）で行う。

## ブートストラップ対策

ルート `.spec/PROJECT.md` の規定と同じく、開発プロセスに適用する bitz-sdd は
リリース済み（main にマージ済み）バージョンに固定する。
