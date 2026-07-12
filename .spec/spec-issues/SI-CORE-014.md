---
id: SI-CORE-014
raised_by: プロジェクト改修計画（2026-07-12 ユーザー要望 3・5。docs/improvement_master_plan.md）
target: plugins/bitz-ddd/skills/*（3段階読み込みと定型スクリプト化）
proposed_change_type: bump
status: open
---
- **目的**: bitz-ddd にも bitz-sdd と同じ3段階読み込み構造と定型処理スクリプト化を適用し、
  DDD 評価・モデリングの再現性とトークン効率を上げる。
- **提案する修正**（スクリプトは**テスト先行**）:
  1. `ddd-evaluate` に `mmi_score.py` を追加 — 12基準×3レイヤーの採点入力（JSON/CSV）から
     MMI 集計と採点表 Markdown を決定的に生成する（現状はエージェントが毎回表を手組みしている）
  2. `ddd-story` / `ddd-model` に成果物雛形生成（stories/ / domain-model.md の frontmatter 付き
     スキャフォールド）を追加する — 採番・配置規則をスクリプトに固定
  3. 各 SKILL.md を SI-CORE-013 と同じ方針で3段階構造に再整理する
     （手法解説は references/、判断だけ本文）
- **対象ファイル**: `tests/`（先行）、`plugins/bitz-ddd/skills/*/scripts/*.py`（新規）、
  `plugins/bitz-ddd/skills/*/SKILL.md` と references/、bitz-ddd マニフェスト bump。
- **確認観点**:
  - スクリプトのテストが先行して green（採点集計の境界値、雛形の書式）
  - 構造変更部分の diff が移動のみであること（SI-CORE-013 と同じレビュー観点）
  - bitz-sdd 併用前提の記述が SI-CORE-007 の依存宣言（bitz-ddd → bitz-sdd）と整合すること
- **影響推定・ロールバック**: bitz-ddd 内で完結。プラグイン単位で revert 可能。
- **依存**: SI-CORE-013（3段階構造の適用パターンを bitz-sdd で確立してから展開）。
