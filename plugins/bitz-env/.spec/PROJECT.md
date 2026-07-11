# bitz-env ワークスペース

bitz-env プラグイン（開発環境展開）の SDD ワークスペース。モノレポ運用
（sdd-core の Monorepo & Workspaces 節）に従う個別ワークスペースであり、
リポジトリ共通規約はルート `.spec/`（CORE-）が持つ。

- ID プレフィックス: `ENV-`（例: `ENV-FR-001`）
- 検証: `python3 plugins/bitz-sdd/skills/sdd-core/scripts/spec_inspect.py plugins/bitz-env`
  （クロスリファレンス解決は `--workspace . plugins/*`）
- テスト: ルート `tests/test_env_guard.py`（ガード契約の unit-test）

## 経緯（ブラウンフィールド開始）

v0.1.0 は製作プラン（人間承認済み）に基づき先に実装された。本ワークスペースは
その実装へ仕様を追いつかせる reverse-derived で開始している（origin に明記）。
以後の変更は通常の SDD フロー（要件 → タスク → 実装 → 検証）で行う。

## 公開契約（軽量レーン禁止・Design Gate 対象）

- 協調アダプタ契約: `skills/env-orchestration/references/collab-contract.md`
- 生成物のマーカー区間形式: `<!-- bitz-env:begin -->` 〜 `<!-- bitz-env:end -->`
- env_guard.py の入出力（Claude Code / Antigravity 両プラットフォームのフック契約）
