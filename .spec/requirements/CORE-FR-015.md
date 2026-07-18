---
id: CORE-FR-015
version: 1.0
status: approved
domain: tooling
priority: medium
origin: SI-CORE-009
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### CORE-FR-015 bitz-flow 定型処理スクリプト（worktree_ops / commit_lint / pr_helper）

- **説明**: Git フローの定型処理を毎回エージェントが生成するトークン浪費と操作ミスを
  なくすため、bitz-flow の各スキルに決定的スクリプトを同梱する。スキル本文は「判断」を、
  スクリプトは「決定的な操作・検査・生成」を担う（3段階読み込み: 本文→scripts）。
  すべてテスト先行で追加し、スクリプトは標準ライブラリのみで単体実行可能とする。
  起票時前提の再検証: SI-CORE-009 本文の「plugins/bitz-flow/skills/*/scripts/」を
  担当スキル別に確定 — worktree_ops は flow-worktree、commit_lint は flow-core
  （コミット規約の所有者）、pr_helper は flow-pr に置く。乖離はこの配置確定のみで趣旨は不変。
- **受入基準 (EARS)**:
  - THEN `plugins/bitz-flow/skills/flow-worktree/scripts/worktree_ops.py` が worktree の
    作成（add）・一覧（list）・マージ後の後片付け（cleanup）・失敗時破棄（discard）の定型操作を
    提供し、状態変更系サブコマンドは**既定で dry-run**（実行するコマンド列の表示のみ）であること SHALL
  - IF 状態変更系サブコマンドを実行モード（`--execute`）で起動し、かつ破棄・削除を伴う場合
    THEN 明示の確認フラグ（`--yes`）なしでは実行せず非ゼロ終了すること SHALL
  - THEN worktree_ops.py はガードレール禁止操作（`git reset --hard` / `git push --force` /
    `git clean -f` / `rm -rf` / `sudo`）をいかなる経路でも呼び出さないこと SHALL
  - THEN `plugins/bitz-flow/skills/flow-core/scripts/commit_lint.py` が Conventional Commits
    タイトル（type 語彙・`!` 破壊的変更・任意 scope）、任意の作業 ID、`Implements:` フッターを
    **読み取り専用**で検査し、適合なら 0 / 違反なら非ゼロの終了コードと違反理由を返すこと SHALL
    （メッセージはファイル・標準入力・git rev-range のいずれからも与えられ、CI から呼べる）
  - THEN `plugins/bitz-flow/skills/flow-pr/scripts/pr_helper.py` が PR 本文雛形
    （目的 / 変更点 / 検証結果、任意で `Closes #N` と `Implements:`）を**生成のみ**行い、
    `gh` 等の外部コマンドを実行しないこと SHALL
  - THEN 3スクリプトは Python 標準ライブラリのみに依存し、スキル本文を読み込まずに
    `python3 <script> --help` が単体で動作すること SHALL
  - THEN flow-worktree / flow-core / flow-pr の各 SKILL.md が同梱スクリプトの使い方
    （呼び出し例と責務境界）を参照する節を持つこと SHALL
  - WHEN `.venv/bin/pytest tests/` を実行する THEN 3スクリプトのテストを含む全件が green で
    あり、テストがスクリプト実装より先にコミットされていること SHALL
  - WHEN `python3 scripts/release_check.py` を実行する THEN bitz-flow の minor bump を含め
    全チェックが PASS すること SHALL
- **検証手段**: `tests/test_worktree_ops.py` / `tests/test_commit_lint.py` /
  `tests/test_pr_helper.py` を先行コミットし、`.venv/bin/pytest` 全件 green を確認する
  （dry-run 既定・確認フラグ・禁止操作不在・終了コード・雛形生成を網羅）。
  release_check.py PASS。テスト先行はコミット順（git log）で確認する（unit-test）。
- **Revision History**:
  - 1.0 (2026-07-18) 初版（draft 起票。起票時前提の補正1件 — スクリプトの担当スキル別配置の確定 — を説明欄に明記）
