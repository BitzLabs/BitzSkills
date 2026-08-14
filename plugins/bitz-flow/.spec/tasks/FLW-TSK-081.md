---
implements: FLW-FR-006, FLW-CON-005, FLW-CON-006, FLW-NFR-011
depends_on: FLW-TSK-080
boundary: scripts/agy_guard.py, evals/flow-core/m2-eval/local_confirmation_subject.py, evals/flow-core/m2-eval/run_local_confirmation.py, evals/flow-core/m2-eval/qualification-2026-08-14-m2-runtime.json, evals/flow-core/m2-eval/active-local-confirmation.json, tests/test_agy_guard.py, tests/test_flow_m2_confirmation.py, plugins/bitz-flow/.spec/specs/m2-exit/test-spec.md, plugins/bitz-flow/.spec/tasks/FLW-TSK-081.md, plugins/bitz-flow/.spec/reviews/FLW-REV-016.md, plugins/bitz-flow/.spec/reviews/FLW-REV-016.json, plugins/bitz-flow/.spec/ROADMAP.md, plugins/bitz-flow/.spec/STATE.md
status: implementing
---

### M2実動confirmationとExit再レビューを完了する

- **作業内容**: 3platformで同一test ID集合を実行し、実Git worktree E2E、hazard 0、residual 0を
  active manifestへ固定する。GP-001/GP-002をFLW-REV-016で再判定する。
- **検証**: qualification再実行、3platform confirmation、全pytest、spec inspect、release check。
