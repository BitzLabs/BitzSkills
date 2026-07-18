# bitz-flow ワークスペース

bitz-flow プラグイン（Git / GitHub 開発フロー: flow-core / flow-worktree / flow-pr）自身の
SDD ワークスペース。モノレポ運用（sdd-core の Monorepo & Workspaces 節）に従う
個別ワークスペースであり、リポジトリ共通規約はルート `.spec/`（CORE-）が持つ。

- ID プレフィックス: `FLW-`（例: `FLW-FR-001`）
- 検証: `python3 scripts/spec inspect --workspace . plugins/*`
  （本モノリポの正規コマンド。クロスリファレンス解決のため常に一括で実行する）

## 経緯（sdd-git からの切り出し）

本ワークスペースは SI-CORE-008（CORE-FR-014、2026-07-18）により新設。スキル内容は
bitz-sdd の sdd-git を SDD 非依存に汎用化して転記したもので、新設時点では sdd-git が
無変更のまま併存する（二重規定の解消 = sdd-git の委譲ポインタ化は SI-CORE-010 が扱う）。
以後の bitz-flow 変更はすべて FLW- 名前空間で起票し、通常の SDD フロー
（要件 → タスク → 実装 → 検証）で行う。

## ブートストラップ対策

ルート `.spec/PROJECT.md` の規定と同じく、開発プロセスに適用する bitz-sdd は
リリース済み（main にマージ済み）バージョンに固定する。
