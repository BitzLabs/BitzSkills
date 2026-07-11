---
id: SI-ENV-021
raised_by: skill-evaluator（evals/env-destroy/report.md TC-04 節・run13 気づき）
target: plugins/bitz-env/skills/env-destroy/SKILL.md frontmatter description
proposed_change_type: bump
status: open
---
- **矛盾/曖昧の内容**: description のトリガー例「bitz-env プラグインを無効化・
  アンインストールする前後に使用する」は文脈上 bitz-env に限定した記述だが、
  例示フレーズ「アンインストールの後始末」は「プラグイン」という語のみを含む
  一般的な入力（例: run13 / TC-04 (a)「プラグインをアンインストールする前に
  後始末しておいて」）とも表層一致してしまう。TC-04(a) では sandbox 上の
  唯一の撤去候補が bitz-env 生成物だったため誤発動は観測されていない
  （`evals/env-destroy/runs/13-tc04/log.md` で判定一致を確認済み）が、複数の
  プラグインが同時に導入された実運用環境では、対象プラグインを取り違えて
  env-destroy が発動する可能性を否定できない。
- **提案する修正**: description に「bitz-env プラグインの」等、対象プラグインを
  明示的に限定する語を強化する（例: トリガー例を「bitz-env プラグインの
  アンインストール前の後始末」のように対象限定を明示する形に言い換える）。
  一般化のポイントとして、特定の入力文言をハードコードするのではなく、
  「対象プラグインを名指しした場合にのみ確実に発動し、他プラグインの文脈とは
  混同しない」記述密度の底上げを提案する。
- **影響推定**: SKILL.md frontmatter description の軽微な文言変更のみ。
  既存の発動ロジック・ワークフロー本体には影響しない。
  **過学習リスクの注記**: 現時点の TC-04 では誤発動は未観測であり、あくまで
  複数プラグイン共存環境における将来リスクへの予防的措置である。優先度は
  低〜中とし、人間の裁定に委ねる。
