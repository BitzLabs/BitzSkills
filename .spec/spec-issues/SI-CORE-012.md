---
id: SI-CORE-012
raised_by: プロジェクト改修計画（2026-07-12 ユーザー要望 3。docs/improvement_master_plan.md）
target: plugins/bitz-sdd/skills/sdd-core/scripts/（起票・status 更新の定型処理が未スクリプト化）
proposed_change_type: bump
status: accepted
---
- **目的**: 要件 / spec-issue / タスクの採番・雛形生成と status 遷移を毎回エージェントが
  手書きしている定型処理をスクリプト化し、書式ブレ・採番衝突・権限逸脱を構造的に防ぐ。
- **提案する修正**（**テスト先行**）:
  1. `spec_scaffold.py` — プレフィックスを検出して次番号を採番し、要件（EARS 雛形）/
     spec-issue / タスクの frontmatter 付き雛形を生成する
  2. `spec_update.py` — status 遷移と STATE.md 更新。sdd-core の権限マトリクスを
     コードで強制する: エージェントが実行できる遷移（例: 起票→open、実装済み→検証待ち）と
     人間専用遷移（draft→approved、open→accepted）を分け、人間専用は
     `--by-human` フラグ明示がない限り拒否する
  3. sdd-core SKILL.md の軽量レーン節・lifecycle.md からスクリプト使用を参照する
- **対象ファイル**: `tests/`（先行）、`plugins/bitz-sdd/skills/sdd-core/scripts/spec_scaffold.py`
  / `spec_update.py`、sdd-core SKILL.md と references/lifecycle.md（参照追記）、マニフェスト bump。
- **確認観点**:
  - テスト先行で green（採番の一意性、雛形が spec_inspect PASS すること、
    権限外遷移の拒否、`--by-human` なしで approved 化できないこと）
  - 生成物が既存の手書きファイル（SI-CORE-001〜003 等）と書式互換であること
- **影響推定・ロールバック**: 追加のみ（既存ファイルの変換はしない）。削除で戻る。
- **依存**: SI-CORE-011（status 集計ロジックの共用。同一 PR 化は不可、順に積む）。
