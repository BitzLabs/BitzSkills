---
id: SI-ENV-002
raised_by: sdd-review REV-001（consistency RVC-201）
target: plugins/bitz-env/.spec/requirements/ENV-FR-003〜007（検証手段）+ evals/env-*/
proposed_change_type: bump
status: proposed
---
- **矛盾/曖昧の内容**: ENV-FR-003〜007 の6要件は verification_method: example-test で
  evals/env-* を参照するが、evals/ 配下の実体が存在しない。approved 済みだが検証手段が
  空のため verified に到達できず、「要件→設計→実装」までで「→検証」が切れている。
  spec_inspect は example-test の実体有無まで検査しないため PASS をすり抜けている。
- **提案する修正**: skill-tester で各スキルのシナリオテストを evals/env-*/ に作成し、
  要件と検証を接続する。着手前は各要件に「検証未実装（verified 保留）」を明示し、
  黙って抜けている状態を解消する。検証接続後に verified へ昇格（人間裁定）。
- **影響推定**: evals/env-init/・env-orchestration/・env-register/・env-doctor/ の新規作成。
  要件本文は verification_method 据え置き、状態遷移（approved→verified）は検証完了後。
  実装コードへの影響なし（テスト成果物の追加）。
