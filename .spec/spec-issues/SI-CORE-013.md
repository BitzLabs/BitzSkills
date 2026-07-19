---
id: SI-CORE-013
raised_by: プロジェクト改修計画（2026-07-12 ユーザー要望 5。docs/improvement_master_plan.md）
target: plugins/bitz-sdd/skills/*/SKILL.md（3段階読み込み構造への再整理）
proposed_change_type: bump
status: rejected
---
- **目的**: bitz-sdd の全スキルを3段階読み込み構造
  （①frontmatter description=常時ロード → ②SKILL.md 本文=薄い判断層 →
  ③references/scripts=必要時のみ）に統一し、スキル発動時の読み込みトークンを削減する。
  **規定内容は一切変えない構造変更のみ**（動作変更は SI-CORE-011/012 側で完了済みの前提）。
- **提案する修正**:
  1. 各 SKILL.md 本文を「いつ・何を判断するか」と参照表に縮約し、手順詳細・書式定義は
     references/ へ移動する（skill-optimizer の progressive disclosure 手法を適用）
  2. 定型処理は本文に書かず「スクリプト名 + 1行の用途」だけ参照する
  3. 移動に伴う相互参照（他スキル・docs/ からのアンカー参照）を追随させる
- **対象ファイル**: `plugins/bitz-sdd/skills/*/SKILL.md`、`plugins/bitz-sdd/skills/*/references/`
  （移動先新規）、bitz-sdd マニフェスト bump。
- **確認観点**:
  - diff が「本文からの移動」であり文言の意味的変更を含まないこと（レビュー観点の中心）
  - skill-validator チェックリスト PASS、release_check / spec_inspect PASS
  - 各 SKILL.md の行数が縮約されていること（目安: 判断表 + 参照表で1画面程度）
- **影響推定・ロールバック**: 構造のみの変更なので単独 revert 可能。
  SI-CORE-014 より先に revert しないこと。
- **依存**: SI-CORE-010（sdd-git 縮退後の姿で再整理するため）、SI-CORE-012（スクリプト参照先の確定）。
- **再裁定**: 2026-07-19 不採用（人間裁定）。SDD-FR-122 の着手時前提再検証で、起票時に想定した
  本文肥大が実測で不成立（bitz-sdd 14スキル中11スキルが本文 1,200〜2,600 文字で目標状態を既に充足。
  起票時点でも 32〜98 行）。唯一大きい sdd-core（6,630 文字）の可搬部分は毎セッション使う定型
  コマンド例であり、references/ へ移すと読み込み往復でトークンが増える方向。前提乖離が提案の
  趣旨自体（トークン削減）を無効化するため実装せず不採用。将来 sdd-core が肥大したら単体で
  再起票する。status の rejected 遷移は SI-SDD-019（accepted→rejected 語彙追加）の実施後に適用する。
