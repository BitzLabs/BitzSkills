---
id: SI-CORE-007
raised_by: プロジェクト改修計画（2026-07-12 ユーザー要望 4-3。docs/improvement_master_plan.md）
target: scripts/release_check.py（プラグイン間依存の検証機構の不在）
proposed_change_type: bump
status: open
---
- **目的**: 並行開発するプラグイン間の依存関係（例: bitz-ddd → bitz-sdd、将来の
  bitz-sdd → bitz-flow）を機械可読に宣言し、release_check で存在・循環を検証できるようにする。
  現状は description の文言でしか依存が表現されておらず、依存切れを検出できない。
- **提案する修正**:
  1. **テスト先行**: `tests/` に依存検証の回帰テストを追加する
     （宣言された依存先が marketplace に存在しない場合 FAIL、循環依存で FAIL、
     依存宣言なしの既存プラグインは PASS のまま）
  2. マニフェスト `metadata.dependencies`（例: `["bitz-sdd>=1.4"]`）の書式を規定し、
     2マニフェスト（Claude Code / Antigravity）で同値を要求する
  3. release_check.py に依存グラフ検証を追加する
  4. init / update / doctor 時の依存確認手順は SI-CORE-006 の標準契約に追記する
- **対象ファイル**: `tests/test_release_check*.py`（先行）、`scripts/release_check.py`、
  plugin-creator の plugin-structure reference（書式の記載）。
- **確認観点**:
  - 新規テストが red → green の順で入っていること（テストコミットが先）
  - 依存宣言を持たない既存5プラグインが引き続き PASS すること（後方互換）
  - `.venv/bin/pytest` 全件 green、release_check PASS
- **影響推定・ロールバック**: release_check の追加検証のみ。検証部と書式規定を revert すれば戻る。
- **依存**: SI-CORE-006（標準契約への追記先）。
