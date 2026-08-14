# bitz-quality ワークスペース

bitz-quality プラグイン（品質管理・多層品質ゲート・テスト設計・多観点レビュー）自身の SDD ワークスペース。
モノレポ運用（sdd-core の Monorepo & Workspaces 節）に従う個別ワークスペースであり、リポジトリ共通規約はルート `.spec/`（CORE-）が持つ。

- ID プレフィックス: `QLT-`（例: `QLT-FR-001`）
- 検証: `python3 scripts/spec inspect --workspace . plugins/*`
- 依存: `bitz-flow>=0.2`
