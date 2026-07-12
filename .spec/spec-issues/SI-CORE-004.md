---
id: SI-CORE-004
raised_by: プロジェクト改修計画（2026-07-12 ユーザー要望。docs/improvement_master_plan.md）
target: plugins/bitz-ddd / plugins/plugin-creator / plugins/skill-creator（個別 .spec 未設置）
proposed_change_type: new
status: open
---
- **目的**: 全プラグインへの sdd-discovery 実施（SI-CORE-005）の前提として、
  個別 SDD ワークスペースが無い3プラグインに `.spec/` を新設する。
  bitz-sdd / bitz-env は新設済み（PR #23 / #22）であり、モノレポ運用
  （sdd-core の Monorepo & Workspaces 節）を全プラグインに揃える。
- **提案する修正**: `plugins/bitz-ddd/.spec/`、`plugins/plugin-creator/.spec/`、
  `plugins/skill-creator/.spec/` に PROJECT.md と空の requirements/ spec-issues/ tasks/ を
  新設する。ID プレフィックスは `DDD-` / `PLG-` / `SKC-`。
- **対象ファイル**: 上記3ディレクトリの新規ファイルのみ（既存ファイルの変更なし）。
- **確認観点**:
  - `python3 plugins/bitz-sdd/skills/sdd-core/scripts/spec_inspect.py --workspace . plugins/*` が PASS
  - `python3 scripts/release_check.py` が引き続き PASS（プラグイン本体に変更がないこと）
  - プレフィックスがルート・他ワークスペースと衝突しないこと
- **影響推定・ロールバック**: 追加のみで挙動変更なし。ディレクトリ削除で完全に戻せる。
- **依存**: なし（最初に実施可能）。
