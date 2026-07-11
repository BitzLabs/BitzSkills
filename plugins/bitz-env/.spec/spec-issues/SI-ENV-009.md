---
id: SI-ENV-009
raised_by: skill-evaluator（evals/env-init/report.md 改善提案2節）
target: plugins/bitz-env/skills/env-init/SKILL.md + references/templates/
proposed_change_type: bump
status: open
---
- **矛盾/曖昧の内容**: env-init のテンプレート（AGENTS-template.md 等）が持つ
  `{{project}}` プレースホルダの決定方法が SKILL.md に明記されていない。
  evals/env-init/runs/4・runs/7（いずれもスキルあり実行）の log.md 備考で、
  実行者がプロンプトに明記のないプロジェクト名を独自に `sample-project` という
  仮値で埋めたことを自己申告しており、決定規則が実行者依存になっている
  （evals/env-init/report.md 改善提案2節に詳細）。
- **提案する修正**: SKILL.md（または references/templates/ の説明）に、
  `{{project}}` 等のプレースホルダの既定決定規則を明記する。例:
  「対象プロジェクトのディレクトリ名を既定値とし、git リポジトリ名が取得できれば
  それを優先する。ユーザーが明示した名称があればそれを優先する」といった優先順位を
  一般規則として定義する。特定のテストケースの入力文をそのまま規則に埋め込むのではなく、
  「プロンプトにプロジェクト名の明示がない場合」というカテゴリ全体に効く規則とする。
- **影響推定**: SKILL.md 手順（生成ステップ）に決定規則の追記1件。テンプレート自体の
  変更は不要。既存の生成済み成果物への遡及的な影響はなし。
