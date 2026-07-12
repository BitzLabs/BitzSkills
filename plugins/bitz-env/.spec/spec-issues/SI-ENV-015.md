---
id: SI-ENV-015
raised_by: skill-evaluator（evals/env-orchestration/report.md TC-03 節・改善提案2）
target: plugins/bitz-env/skills/env-orchestration/SKILL.md（合議型の進め方）
proposed_change_type: bump
status: accepted
---
- **矛盾/曖昧の内容**: 「合議型の進め方」節は合議メンバーを「advisor、アダプタの review
  役割、必要なら worker」と記述するが、「必要なら」の判定基準が SKILL.md 本文に定義されて
  いない。「パターン選択の決定木」の合議型の枝（影響が大きい: 破壊的変更・セキュリティ関連・
  ユーザー明示要求）にも worker を合議に含める条件への言及は無い。
  evals/env-orchestration/runs/08/answer.md（TC-03 スキルあり実行）では、実行者が worker を
  合議メンバーから明示的に除外しているが、その理由（「決定木上は『必要なら worker』の位置
  づけで今回の議題は設計判断のため対象外」）は実行者が独自に補ったものであり、SKILL.md 本文
  から一意に導出できるものではない。同種の議題でも、worker を含めるべきか除外すべきか
  実行者・モデルによって判断が割れるおそれがある。
- **提案する修正**: 「合議型の進め方」節、または決定木の合議型の枝に、worker を合議
  メンバーに含める一般的な判断基準を追記する（例:「争点に実装可否・工数見積もりなど
  実行観点の意見が含まれる場合は worker も招集する。純粋な設計選定・原因調査など実行観点を
  伴わない議題では advisor / review のみで足りる」）。特定テストケースの議題名を条件に
  埋め込むのではなく、議題の性質による一般化した基準とする。
- **影響推定**: SKILL.md「合議型の進め方」節の記述追加（軽微・後方互換）。
  evals/env-orchestration/cases.md TC-03 に「worker を含めるか否かの判断過程を成果物に
  明記しているか」のアサーションを追加する余地がある（要件化後、skill-tester 側の対応）。
- **裁定記録**: 2026-07-12 人間裁定（チャット指示「残りのISSUEを進めましょう」）により accepted。提案どおり反映する（既存要件の範囲内の記述明確化のため新規要件は起票しない = 軽量レーン）。
- **実施**: 2026-07-12 対象 SKILL.md へ反映済み（スキル metadata version を patch bump）。
