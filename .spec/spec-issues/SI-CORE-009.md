---
id: SI-CORE-009
raised_by: プロジェクト改修計画（2026-07-12 ユーザー要望 3。docs/improvement_master_plan.md）
target: plugins/bitz-flow/skills/*/scripts/（定型処理スクリプトの不在）
proposed_change_type: bump
status: open
---
- **目的**: Git フローの定型処理を毎回エージェントが生成するトークン浪費と操作ミスを
  なくす。スキル本文は「判断」だけを残し、決定的な操作はスクリプトに固定する。
- **提案する修正**（いずれも**テスト先行**で追加）:
  1. `worktree_ops.py` — worktree の作成 / 破棄 / マージバックの定型操作
     （破棄は確認プロンプト必須。`git reset --hard` 等のガードレール禁止操作は実装しない）
  2. `commit_lint.py` — Conventional Commits + タスク ID + Implements フッターの検査
     （読み取り専用。CI からも呼べる終了コード設計）
  3. `pr_helper.py` — PR 本文（目的 / 変更点 / 検証結果）の雛形生成（生成のみ、gh 実行はしない）
  4. 各スキル本文からスクリプトの使い方を参照する（3段階読み込み: 本文→scripts）
- **対象ファイル**: `tests/`（先行）、`plugins/bitz-flow/skills/*/scripts/*.py`、
  各 SKILL.md のスクリプト参照節、bitz-flow マニフェスト bump。
- **確認観点**:
  - テストが先にコミットされ、`.venv/bin/pytest` 全件 green
  - スクリプト単体で python3 実行可能（スキル読み込みなしで動く＝トークン0で再利用可）
  - 状態変更系（worktree_ops）が dry-run をデフォルトとし、破壊的操作を含まないこと
- **影響推定・ロールバック**: bitz-flow 内で完結。スクリプトとテストの削除で戻る。
- **依存**: SI-CORE-008（bitz-flow の存在）。
