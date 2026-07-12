---
id: SI-CORE-005
raised_by: プロジェクト改修計画（2026-07-12 ユーザー要望。docs/improvement_master_plan.md）
target: plugins/*/.spec/discovery/（全プラグインの上流探索成果物）
proposed_change_type: new
status: accepted
---
- **目的**: 各開発プラグインの目的・成功指標・スコープを明文化し、以後の改修
  （bitz-flow 切り出し・共通スキル抽出・3段階化）の判断根拠を discovery 成果物として残す。
- **提案する修正**: sdd-discovery を各プラグインで実施し、
  `plugins/<name>/.spec/discovery/` に Vision Board / North Star Metric / MoSCoW /
  JTBD ペルソナ / Go-No-Go 裁定を作成する。対象は bitz-sdd / bitz-env / bitz-ddd /
  plugin-creator / skill-creator の5つ（bitz-flow は SI-CORE-008 の新設時に実施）。
  1プラグイン = 1コミットに分けてレビュー可能にする。
- **対象ファイル**: `plugins/*/.spec/discovery/DSC-*.md`（新規のみ）。
  docs/01-context/ への展開は sdd-docs の pull を使う場合のみ。
- **確認観点**:
  - 各プラグインの Go / No-Go 裁定が明記されていること（No-Go 判定が出た場合は
    後続 ISSUE のスコープ見直しを人間に差し戻す）
  - spec_inspect の一括検証が PASS を維持すること
- **影響推定・ロールバック**: ドキュメント追加のみ。プラグイン単位で revert 可能。
- **依存**: SI-CORE-004（3プラグインのワークスペース新設）。
