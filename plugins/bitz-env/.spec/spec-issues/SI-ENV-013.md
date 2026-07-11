---
id: SI-ENV-013
raised_by: skill-evaluator（evals/env-register/report.md 改善提案3、TC-03 節）
target: plugins/bitz-env/skills/env-register/SKILL.md（「#### 名前衝突の検出と解決」L68-80、特に例示 L76）
proposed_change_type: bump
status: open
---
- **矛盾/曖昧の内容**: SKILL.md L76 の例（「`delegate` が衝突するなら
  `bitz-collab-example-delegate` として routes に記録」）は `<アダプタ名>-<役割名>` 形式の
  一例のみを示しており、命名規則としての一般則が明文化されていない。
  evals/env-register/runs/08（TC-03）ではこの読みで `second-adapter-delegate` を採用し
  アサーションは満たしたが、run08 ログの「気づき」節は「実スキル名（`ex-delegate`）を
  活かした `<アダプタ名>-<実スキル名>`（例: `second-adapter-ex-delegate`）という読み方も
  文面上は排除できず、曖昧さが残る」と指摘している。今回は挙動のブレとして顕在化しな
  かった（合否に影響なし）が、例が1件のみのため将来的な実装揺れの余地が残る。
- **提案する修正**: L76 の例の直前（またはセクション冒頭）に、命名規則を一般則として
  明記する一文を追加する。例:「命名規則: 常に `<アダプタ名>-<役割名>` とする
  （実スキル名は使わない）」。特定ケースの期待値をハードコードする提案ではなく、
  衝突解決全般に適用される命名規則の明文化であり、過学習リスクは低い。
- **影響推定**: SKILL.md 本文の記述追加のみ（既存の挙動・例は変更しない、曖昧さの解消）。
  version bump（patch）。優先度低のため他の SI-ENV-011/012 と合わせて着手する形でよい。
